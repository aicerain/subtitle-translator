"""
翻译模块 - 支持多家大模型 API,把字幕段落批量翻译到目标语言。

策略:
- 把字幕段落分批(默认每批 30 段),拼成带编号的文本喂给 LLM
- 要求模型严格按编号返回,然后解析回每段译文
- 任何一家 API 都通过 system + user prompt 走 chat completion 接口
- OpenAI / DeepSeek / Qwen / Zhipu / 自定义,统一走 OpenAI SDK 即可(它们都兼容)
- Anthropic 用官方 anthropic SDK
"""
from __future__ import annotations
import re
import time
from dataclasses import dataclass
from typing import Callable, Optional

from .transcriber import Segment


ProgressCb = Optional[Callable[[str, float], None]]


SYSTEM_PROMPT = """你是一位专业的视频字幕翻译专家。你的任务是把用户给出的字幕翻译成目标语言。

要求:
1. 严格逐条翻译,不合并、不拆分、不增删任何一条。
2. 必须保持原编号 [1] [2] ... 与原条目一一对应。
3. 翻译要符合口语习惯,简洁自然,符合目标语言的表达方式。
4. 不要输出任何解释、说明、前后缀,只输出 [编号] 译文 的格式,一行一条。
5. 保留原文中的专有名词(人名、地名、品牌)的常用译法。
6. 如果遇到无法识别或不需要翻译的内容(纯符号、数字),原样保留。"""


USER_TEMPLATE = """请把下面的字幕从「{source_lang}」翻译成「{target_lang}」。

{batch}

请按 [编号] 译文 的格式逐行输出译文。"""


# ------- 原文润色 Prompt(只校对、不翻译)-------

POLISH_SYSTEM_PROMPT = """你是一位严谨的字幕校对员。用户会给你一段语音识别(ASR)产出的字幕,你要做"原语言校对",不做任何翻译。

允许做的修改:
1. 补全或纠正标点(中文常缺标点,需补全句号、逗号、问号等)。
2. 纠正同音字 / 明显的识别错字。
3. 删除明显的"幻觉文字",如:与上下文完全无关的"感谢观看""字幕组制作""请关注 XXX"等莫名出现的语句。
4. 把同一句被重复输出 N 次的内容合并为 1 次。
5. 修正大小写错误(英文)。

严禁做的事:
1. 不要翻译成别的语言。输入是什么语言,输出就是什么语言。
2. 不要合并、不要拆分、不要删除任何编号(除非整条都是幻觉,这种极端情况可以输出"[N] " 后留空)。
3. 不要改变原意,不要演绎,不要补充原文没有的信息。
4. 不要加任何解释或前后缀,只输出 [编号] 校对后文本 的格式。

输出格式严格为每行一条 [编号] 校对后的文本。"""


POLISH_USER_TEMPLATE = """请校对下面用「{lang}」识别出的字幕条目,只做轻量修正,不要翻译。

{batch}

请按 [编号] 校对后的文本 的格式逐行输出。"""


@dataclass
class TranslatorConfig:
    provider: str       # openai / anthropic / deepseek / qwen / zhipu / custom
    api_key: str
    base_url: str
    model: str


class Translator:
    def __init__(
        self,
        cfg: TranslatorConfig,
        batch_size: int = 50,         # 单批最多多少条字幕
        max_batch_chars: int = 4000,  # 单批最多多少输入字符(防 token 超限)
        parallel_workers: int = 4,    # 云端最大并发批次;本地服务器会强制为 1
        max_output_tokens: int = 8000,  # API 调用允许的最大输出 tokens
    ):
        self.cfg = cfg
        self.batch_size = max(1, int(batch_size))
        self.max_batch_chars = max(200, int(max_batch_chars))
        self.parallel_workers = max(1, int(parallel_workers))
        self.max_output_tokens = max(512, int(max_output_tokens))

    def translate_segments(
        self,
        segments: list[Segment],
        source_language: str,
        target_language: str,
        progress_cb: ProgressCb = None,
    ) -> list[str]:
        """
        翻译所有段落的文本,返回与 segments 一一对应的译文列表。
        """
        return self._run_batched(
            segments,
            source_language=source_language,
            target_language=target_language,
            mode="translate",
            progress_cb=progress_cb,
            done_msg="翻译完成 ✓",
            stage_msg="翻译",
        )

    def polish_segments(
        self,
        segments: list[Segment],
        language: str,
        progress_cb: ProgressCb = None,
    ) -> list[str]:
        """
        用 LLM 对 Whisper 输出做原语言校对(修标点/错字/幻觉/重复),不翻译。
        返回与 segments 一一对应的修正后文本。
        """
        return self._run_batched(
            segments,
            source_language=language,
            target_language=language,
            mode="polish",
            progress_cb=progress_cb,
            done_msg="原文润色完成 ✓",
            stage_msg="润色",
        )

    def _run_batched(
        self,
        segments: list[Segment],
        source_language: str,
        target_language: str,
        mode: str,
        progress_cb: ProgressCb,
        done_msg: str,
        stage_msg: str,
    ) -> list[str]:
        """翻译/润色的批处理。
        - 云端 provider:用线程池并发(默认 4 worker),典型加速 3-4 倍。
        - 本地 provider (LM Studio / Ollama 等):强制串行,单模型无法真并行。
        - 单批失败:自动降级为逐条重试,任何一条最终失败保留原文。
        """
        from .config_languages import lang_display
        import concurrent.futures
        import threading

        output: list[str] = [""] * len(segments)
        non_empty = [i for i, s in enumerate(segments) if s.text.strip()]
        if not non_empty:
            return output

        src_name = lang_display(source_language)
        tgt_name = lang_display(target_language)

        # 本地服务器(LM Studio / Ollama)单次能稳定处理的批量小,降级阈值
        # 防止 MLX/llama.cpp 在大 batch 时状态污染或 OOM
        is_local = self._is_local_server()
        effective_batch_size = min(self.batch_size, 25) if is_local else self.batch_size
        effective_max_chars = min(self.max_batch_chars, 2000) if is_local else self.max_batch_chars

        # 自适应打包:同时满足 (条数 ≤ batch_size) AND (字符数 ≤ max_batch_chars)
        batches: list[list[int]] = []
        current: list[int] = []
        current_chars = 0
        for idx in non_empty:
            text_len = len(segments[idx].text)
            if current and (
                len(current) >= effective_batch_size
                or current_chars + text_len > effective_max_chars
            ):
                batches.append(current)
                current = []
                current_chars = 0
            current.append(idx)
            current_chars += text_len
        if current:
            batches.append(current)
        total = len(batches)
        avg_per_batch = (len(non_empty) / max(total, 1)) if total else 0

        # 本地服务器(LM Studio / Ollama / localhost)强制串行
        # 同一个本地模型同时收多请求只会排队,反而拖慢
        workers = 1 if is_local else self.parallel_workers
        # 批数少时也没必要开太多 worker
        workers = min(workers, total)

        if progress_cb:
            mode_desc = f"串行(本地模型)" if workers == 1 else f"并发 {workers} 路"
            progress_cb(
                f"{stage_msg}开始:{len(non_empty)} 段 → 自适应打包成 {total} 批 "
                f"(平均 {avg_per_batch:.0f} 段/批),{mode_desc}",
                0.0,
            )

        completed_lock = threading.Lock()
        completed = [0]

        def _call_with_retries(texts: list[str], retries: int = 2) -> list[str]:
            """单批调用,瞬时错误自动重试(指数退避)"""
            import time
            last_err: Optional[Exception] = None
            for attempt in range(retries + 1):
                try:
                    return self._call_llm(texts, src_name, tgt_name, mode=mode)
                except Exception as e:
                    last_err = e
                    if attempt < retries and _is_retryable_error(e):
                        backoff = 0.5 * (2 ** attempt)   # 0.5s, 1s, 2s
                        if progress_cb:
                            progress_cb(
                                f"  瞬时错误,{backoff:.1f}s 后重试({attempt+1}/{retries}):{_short_err(e)}",
                                -1,
                            )
                        time.sleep(backoff)
                        continue
                    raise
            # 不应到达
            if last_err:
                raise last_err
            return []

        def _process_batch(idxs: list[int]) -> tuple[list[int], list[str]]:
            """执行一个批次,返回 (索引列表, 结果列表)。
            重试 2 次仍失败 → 逐条降级。"""
            texts = [segments[i].text for i in idxs]
            try:
                results = _call_with_retries(texts)
            except Exception as e:
                if progress_cb:
                    progress_cb(f"⚠ 单批失败 ({_short_err(e)}),回退逐条...", -1)
                results = []
                for t in texts:
                    try:
                        single = self._call_llm([t], src_name, tgt_name, mode=mode)
                        results.append(single[0] if single else t)
                    except Exception:
                        results.append(t)   # 最坏:保留原文
            return idxs, results

        def _on_one_batch_done(idxs: list[int], results: list[str]):
            for oi, txt in zip(idxs, results):
                output[oi] = txt or segments[oi].text
            with completed_lock:
                completed[0] += 1
                done = completed[0]
            if progress_cb:
                progress_cb(
                    f"{stage_msg}进度: {done}/{total} 批已完成",
                    done / max(total, 1),
                )

        if workers == 1:
            # 串行路径
            for idxs in batches:
                ridxs, results = _process_batch(idxs)
                _on_one_batch_done(ridxs, results)
        else:
            # 并发路径
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
                futures = [ex.submit(_process_batch, idxs) for idxs in batches]
                for fut in concurrent.futures.as_completed(futures):
                    try:
                        idxs, results = fut.result()
                        _on_one_batch_done(idxs, results)
                    except Exception as e:
                        # 一个批次彻底失败(包括逐条降级也挂了),原段落保留
                        if progress_cb:
                            progress_cb(f"⚠ 批次完全失败: {e}", -1)

        if progress_cb:
            progress_cb(done_msg, 1.0)
        return output

    # ----------- 内部:具体 LLM 调用 -----------

    def _call_llm(
        self, texts: list[str], src_name: str, tgt_name: str,
        mode: str = "translate",
    ) -> list[str]:
        """调用 LLM 处理一个批次。mode: 'translate' 或 'polish'"""
        if not texts:
            return []
        batch_str = "\n".join(f"[{i + 1}] {t}" for i, t in enumerate(texts))

        if mode == "polish":
            system_prompt = POLISH_SYSTEM_PROMPT
            user_prompt = POLISH_USER_TEMPLATE.format(lang=src_name, batch=batch_str)
        else:
            system_prompt = SYSTEM_PROMPT
            user_prompt = USER_TEMPLATE.format(
                source_lang=src_name, target_lang=tgt_name, batch=batch_str,
            )

        if self.cfg.provider == "anthropic":
            raw = self._call_anthropic(user_prompt, system_prompt)
        else:
            raw = self._call_openai_compatible(user_prompt, system_prompt)

        return self._parse_response(raw, expected=len(texts))

    def _call_openai_compatible(self, user_prompt: str, system_prompt: str = SYSTEM_PROMPT) -> str:
        try:
            from openai import OpenAI
        except ImportError as e:
            raise RuntimeError("未安装 openai 库") from e

        if not self.cfg.api_key:
            raise RuntimeError(f"{self.cfg.provider} 的 API key 未配置")
        if not self.cfg.base_url:
            raise RuntimeError(f"{self.cfg.provider} 的 base_url 未配置")
        if not self.cfg.model:
            raise RuntimeError(f"{self.cfg.provider} 的 model 未配置")

        extra_body: dict = {}
        is_local_provider = self._is_local_server()
        msgs_system = system_prompt
        msgs_user = user_prompt

        if is_local_provider:
            # 1) ttl 防 LM Studio 自动卸载模型
            extra_body["ttl"] = 3600
            # 2) 关闭思考模式 — Qwen3 / DeepSeek-R1 / GLM-4-Thinking 等
            #    思考型模型如果不关,会把绝大部分 max_tokens 用在"内部 self-talk"上,
            #    真正的译文输出可能被截断,且巨大的 thinking KV cache 还会污染
            #    后续请求(踩到 MLX 引擎的 tree_reduce bug)
            extra_body["enable_thinking"] = False   # Qwen3 / GLM 系列 API 参数
            extra_body["chat_template_kwargs"] = {"enable_thinking": False}  # 另一种命名
            # 3) 在 system prompt 末尾追加 /no_think 指令
            #    这是 Qwen3 模型识别的"显式禁用思考"指令,对非思考模型也无害
            msgs_system = system_prompt + "\n\n/no_think"

        client = OpenAI(
            api_key=self.cfg.api_key,
            base_url=self.cfg.base_url,
            timeout=180,
        )
        resp = client.chat.completions.create(
            model=self.cfg.model,
            messages=[
                {"role": "system", "content": msgs_system},
                {"role": "user", "content": msgs_user},
            ],
            temperature=0.3,
            max_tokens=self.max_output_tokens,
            extra_body=extra_body or None,
        )
        return resp.choices[0].message.content or ""

    def _is_local_server(self) -> bool:
        """识别是否在调本地服务器 (LM Studio / Ollama / vLLM 等)。
        本地服务器需要特殊处理(ttl 防卸载,更长 timeout)。
        """
        if self.cfg.provider == "lmstudio":
            return True
        # 自定义 / 任何 provider,只要 base_url 是本地地址就当本地处理
        url = (self.cfg.base_url or "").lower()
        return any(host in url for host in (
            "127.0.0.1", "localhost", "0.0.0.0", "::1",
        ))

    def _call_anthropic(self, user_prompt: str, system_prompt: str = SYSTEM_PROMPT) -> str:
        try:
            from anthropic import Anthropic
        except ImportError as e:
            raise RuntimeError("未安装 anthropic 库") from e

        if not self.cfg.api_key:
            raise RuntimeError("Anthropic API key 未配置")

        kwargs = {}
        if self.cfg.base_url:
            kwargs["base_url"] = self.cfg.base_url
        client = Anthropic(api_key=self.cfg.api_key, **kwargs)

        resp = client.messages.create(
            model=self.cfg.model or "claude-sonnet-4-5",
            max_tokens=self.max_output_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        # anthropic 返回 content 是 list[ContentBlock]
        parts = []
        for blk in resp.content:
            if getattr(blk, "type", None) == "text":
                parts.append(blk.text)
        return "".join(parts)

    @staticmethod
    def _parse_response(raw: str, expected: int) -> list[str]:
        """从模型回复里抽出 [n] 译文 的行,按编号排序"""
        results = [""] * expected
        # 思考型模型(Qwen3/DeepSeek-R1)可能仍输出 <think>..</think> 包裹的思考过程,
        # 即使我们已请求关闭。先把这部分清掉只保留真正的回答。
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE)
        raw = re.sub(r"<thinking>.*?</thinking>", "", raw, flags=re.DOTALL | re.IGNORECASE)
        # 匹配每行 [数字] 内容
        pattern = re.compile(r"^\s*\[\s*(\d+)\s*\]\s*(.+?)\s*$", re.MULTILINE)
        for m in pattern.finditer(raw):
            idx = int(m.group(1)) - 1
            if 0 <= idx < expected:
                results[idx] = m.group(2).strip()

        # 兜底:如果没匹配到任何编号,按行序填入
        if all(not x for x in results):
            lines = [l.strip() for l in raw.splitlines() if l.strip()]
            for i, line in enumerate(lines[:expected]):
                # 去掉可能的编号前缀
                cleaned = re.sub(r"^\[?\d+\]?[.\)、:\s]*", "", line)
                results[i] = cleaned

        return results


# ===== 错误处理工具 =====

# 这些错误模式说明可重试(瞬时问题,不是配置错):
_RETRYABLE_PATTERNS = (
    "timeout", "timed out", "time out",
    "connection", "reset by peer", "broken pipe",
    "temporarily", "try again",
    "tree_reduce", "iterating prediction stream",   # LM Studio MLX 引擎 bug
    "ratelimit", "rate limit", "rate_limit", "429",
    "internal server error", "500", "502", "503", "504",
    "overloaded",
    "context deadline exceeded",
    "ssl", "eof",
)


def _is_retryable_error(err: Exception) -> bool:
    """判断异常是否值得重试(瞬时性 vs 配置/语义错)"""
    msg = str(err).lower()
    return any(p in msg for p in _RETRYABLE_PATTERNS)


def _short_err(err: Exception) -> str:
    """提取错误的可读关键文本,避免日志被大段 JSON / traceback 淹没"""
    msg = str(err)
    import re
    # 常见模式 1: Error code: 400 - {'error': "实际信息..."}  (LM Studio / OpenAI 兼容)
    # 用 greedy 匹配到末尾的引号 + } 包裹
    m = re.search(r"['\"]error['\"]\s*:\s*['\"](.+?)['\"]\s*[,}]", msg, re.DOTALL)
    if m:
        return m.group(1)[:300]
    # 常见模式 2: openai SDK 的 "Error code: 400 - <body>"
    m = re.search(r"Error code:\s*\d+\s*-\s*(.+)", msg)
    if m:
        return m.group(1)[:300]
    # 截断超长
    if len(msg) > 250:
        return msg[:250] + "..."
    return msg


def build_translator(config: dict) -> Translator:
    """根据 config 字典构造翻译器"""
    provider = config.get("translator_provider", "openai")
    sub = config.get("translator_configs", {}).get(provider, {})
    cfg = TranslatorConfig(
        provider=provider,
        api_key=sub.get("api_key", ""),
        base_url=sub.get("base_url", ""),
        model=sub.get("model", ""),
    )
    # 允许用户在 config 顶层调整
    workers = int(config.get("translator_parallel_workers", 4))
    batch_size = int(config.get("translator_batch_size", 50))
    max_batch_chars = int(config.get("translator_max_batch_chars", 4000))
    max_output_tokens = int(config.get("translator_max_output_tokens", 8000))
    return Translator(
        cfg,
        batch_size=batch_size,
        max_batch_chars=max_batch_chars,
        parallel_workers=workers,
        max_output_tokens=max_output_tokens,
    )
