"""
语音识别模块 - 把音频转成带时间戳的字幕段落。

提供统一接口 Transcriber.transcribe(audio_path) -> list[Segment]
两种实现:
- FasterWhisperTranscriber: 本地 faster-whisper(默认/推荐)
- OpenAIWhisperAPITranscriber: 调 OpenAI Whisper API

Segment 字段:
    start: float    起始秒
    end: float      结束秒
    text: str       识别文本
    language: str   语种 (识别出的语种代码,可能为空)
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Iterable, Optional


@dataclass
class Segment:
    start: float
    end: float
    text: str
    language: str = ""


# 单段字幕最长持续时间(秒)
# 现实中人说一句话很少超过 8 秒;Whisper 偶尔会把静默段也算进上一句的 end,
# 导致一句话显示 30 秒甚至 30 分钟。超过此阈值的段会被截断。
MAX_SEGMENT_DURATION = 12.0


ProgressCb = Optional[Callable[[str, float], None]]


class TranscriberBase:
    """识别器抽象接口"""

    def transcribe(
        self,
        audio_path: str,
        source_language: str = "auto",
        progress_cb: ProgressCb = None,
    ) -> tuple[list[Segment], str]:
        """
        识别音频,返回 (段落列表, 检测到/使用的语种代码)。
        progress_cb(message, fraction[0-1]) 可选回调。
        """
        raise NotImplementedError


# ---------------- Faster-Whisper (本地) ----------------


class FasterWhisperTranscriber(TranscriberBase):
    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "auto",
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise RuntimeError(
                "未安装 faster-whisper。请运行: pip install faster-whisper"
            ) from e

        device = self.device
        compute_type = self.compute_type

        # auto 设备 / compute_type 选择
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"

        if compute_type == "auto":
            compute_type = "float16" if device == "cuda" else "int8"

        self._model = WhisperModel(
            self.model_size,
            device=device,
            compute_type=compute_type,
        )
        return self._model

    def transcribe(
        self,
        audio_path: str,
        source_language: str = "auto",
        progress_cb: ProgressCb = None,
    ) -> tuple[list[Segment], str]:
        model = self._load_model()
        if progress_cb:
            progress_cb(f"加载 Whisper 模型完成 ({self.model_size}), 开始识别...", 0.0)

        # faster-whisper 用 None 表示自动检测
        lang_arg = None if source_language == "auto" else source_language

        segments_iter, info = model.transcribe(
            audio_path,
            language=lang_arg,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            # 关闭"基于上文条件采样":Whisper 默认开启后会用前一段输出做下一段提示,
            # 大段静音/纯音乐场景下容易让一句话的 end 时间被拉到下一句的 start,
            # 导致单段时长几十分钟。关掉后每段独立,稳定性大幅提升。
            condition_on_previous_text=False,
        )

        detected_lang = info.language or source_language
        total_duration = info.duration or 1.0

        result: list[Segment] = []
        for seg in segments_iter:
            result.append(Segment(
                start=seg.start,
                end=seg.end,
                text=(seg.text or "").strip(),
                language=detected_lang,
            ))
            if progress_cb and total_duration > 0:
                frac = min(1.0, seg.end / total_duration)
                progress_cb(f"识别中: {_fmt_time(seg.end)} / {_fmt_time(total_duration)}", frac)

        # 后处理:截断异常长的段(Whisper 偶尔会把静默并入上一段)
        result = _clip_long_segments(result, progress_cb)

        if progress_cb:
            progress_cb(f"识别完成,共 {len(result)} 段。检测语种: {detected_lang}", 1.0)
        return result, detected_lang


# ---------------- OpenAI Whisper API ----------------


class OpenAIWhisperAPITranscriber(TranscriberBase):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "whisper-1",
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    def transcribe(
        self,
        audio_path: str,
        source_language: str = "auto",
        progress_cb: ProgressCb = None,
    ) -> tuple[list[Segment], str]:
        if not self.api_key:
            raise RuntimeError("OpenAI Whisper API key 未配置")

        try:
            from openai import OpenAI
        except ImportError as e:
            raise RuntimeError("未安装 openai 库,请运行: pip install openai") from e

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        if progress_cb:
            progress_cb("上传音频到 OpenAI Whisper API...", 0.1)

        kwargs = dict(
            model=self.model,
            response_format="verbose_json",   # 拿到 segments + timestamps
            timestamp_granularities=["segment"],
        )
        if source_language != "auto":
            kwargs["language"] = source_language

        with open(audio_path, "rb") as f:
            resp = client.audio.transcriptions.create(file=f, **kwargs)

        if progress_cb:
            progress_cb("识别完成,解析结果...", 0.9)

        # OpenAI 返回的对象有 .segments / .language
        segments_data = getattr(resp, "segments", None) or []
        detected_lang = getattr(resp, "language", source_language) or source_language

        result: list[Segment] = []
        for s in segments_data:
            # SDK 返回的可能是 dict 或对象
            start = s["start"] if isinstance(s, dict) else s.start
            end = s["end"] if isinstance(s, dict) else s.end
            text = s["text"] if isinstance(s, dict) else s.text
            result.append(Segment(
                start=float(start),
                end=float(end),
                text=(text or "").strip(),
                language=detected_lang,
            ))

        # 如果没有 segments,把整段文本当成一个段落
        if not result and getattr(resp, "text", None):
            result.append(Segment(
                start=0.0, end=0.0, text=resp.text.strip(), language=detected_lang
            ))

        # 同样截断异常长的段(API 也可能输出超长段)
        result = _clip_long_segments(result, progress_cb)

        if progress_cb:
            progress_cb(f"识别完成,共 {len(result)} 段。语种: {detected_lang}", 1.0)
        return result, detected_lang


def _clip_long_segments(
    segments: list[Segment],
    progress_cb: ProgressCb = None,
) -> list[Segment]:
    """
    把异常长的段截断到 MAX_SEGMENT_DURATION 秒。
    现实中一句台词不会超过 8 秒,Whisper 偶尔输出几十秒甚至几十分钟的段(把静默
    /纯音乐段并入上一句的 end)。这里硬截断,保证字幕显示时长合理。
    """
    clipped_count = 0
    longest_before = 0.0
    for seg in segments:
        dur = seg.end - seg.start
        if dur > longest_before:
            longest_before = dur
        if dur > MAX_SEGMENT_DURATION:
            seg.end = seg.start + MAX_SEGMENT_DURATION
            clipped_count += 1

    if clipped_count > 0:
        msg = (
            f"⚠ 后处理:{clipped_count} 段时长异常(最长 {longest_before:.0f}s),"
            f"已截断到 {MAX_SEGMENT_DURATION:.0f}s"
        )
        if progress_cb:
            progress_cb(msg, -1)
    return segments


def _fmt_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def build_transcriber(config: dict) -> TranscriberBase:
    """根据 config 字典构造合适的识别器"""
    engine = config.get("asr_engine", "faster-whisper")
    if engine == "openai-api":
        return OpenAIWhisperAPITranscriber(
            api_key=config.get("openai_whisper_api_key", ""),
            base_url=config.get("openai_whisper_base_url", "https://api.openai.com/v1"),
            model=config.get("openai_whisper_model", "whisper-1"),
        )
    return FasterWhisperTranscriber(
        model_size=config.get("whisper_model_size", "base"),
        device=config.get("whisper_device", "auto"),
        compute_type=config.get("whisper_compute_type", "auto"),
    )
