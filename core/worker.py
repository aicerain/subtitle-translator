"""
后台 Worker 线程:串联 提取音频 → ASR → 翻译 → 写 SRT → (可选) 烧录
通过 QThread 信号与 GUI 通信。
"""
from __future__ import annotations
import os
import tempfile
import threading
import traceback
from pathlib import Path
from typing import Optional, Callable

from PyQt6.QtCore import QThread, pyqtSignal


class CancelledError(Exception):
    """用户取消时的统一异常,在 worker.run() 里被捕获"""
    pass

from .transcriber import Segment, build_transcriber
from .translator import build_translator
from .subtitle import write_srt
from . import video as video_utils
from . import cache as cache_mod


class SubtitleWorker(QThread):
    """字幕生成工作线程。

    阶段:
      1. 提取音频
      2. 语音识别 → segments
      3. 如目标语言 != 源语言: 翻译
      4. 写 SRT 文件
      5. 发出 ready_for_preview 信号(中断,等用户编辑后调 continue_with_segments)
      6. 如启用烧录:把字幕烧到视频
      7. 完成
    """

    # 信号
    log = pyqtSignal(str)                              # 文本日志
    progress = pyqtSignal(int)                         # 0-100
    stage_changed = pyqtSignal(str)                    # 当前阶段名
    ready_for_preview = pyqtSignal(str, list, list)    # srt_path, segments, translations
    finished_ok = pyqtSignal(str, str)                 # srt_path, burned_video_path("" if none)
    failed = pyqtSignal(str)                           # 错误消息
    cancelled = pyqtSignal()                            # 用户主动取消

    def __init__(
        self,
        video_path: str,
        config: dict,
        target_language: str,
        source_language: str = "auto",
        subtitle_mode: str = "bilingual",   # original / translated / bilingual
        polish_original: bool = False,      # 是否用 LLM 润色 Whisper 原文
        burn: bool = False,
        output_dir: Optional[str] = None,
        preview_before_burn: bool = True,
    ):
        super().__init__()
        self.video_path = video_path
        self.config = config
        self.target_language = target_language
        self.source_language = source_language
        self.subtitle_mode = subtitle_mode
        self.polish_original = polish_original
        self.burn = burn
        self.output_dir = output_dir or str(Path(video_path).parent)
        self.preview_before_burn = preview_before_burn

        # 中断/继续控制
        self._wait_for_user = False
        self._user_continue = False
        self._user_cancel = False
        self._cancel_event = threading.Event()   # 用于在迭代点协作中断
        self._final_segments: list[Segment] = []
        self._final_translations: list[str] = []
        self._srt_path = ""

        self._tmp_audio: Optional[str] = None

    # ------- 给 GUI 调用的控制方法 -------

    def cancel(self) -> None:
        """请求取消。设置事件让所有迭代点 / 等待循环看到。"""
        self._user_cancel = True
        self._user_continue = True   # 解除预览等待
        self._cancel_event.set()      # 让进度回调下次被调用时抛 CancelledError

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def _check_cancelled(self) -> None:
        """在阶段交界处主动调用,被取消立刻抛出"""
        if self._cancel_event.is_set():
            raise CancelledError()

    def _wrap_progress_cb(self, base_cb: Callable[[str, float], None]) -> Callable[[str, float], None]:
        """包装进度回调:每次被调用前先检查是否已取消。
        Whisper 在每段字幕产出时会调一次,翻译在每批完成时调一次,
        因此调用频率足够支撑"几秒内响应取消"。
        """
        def wrapped(msg, frac=0.0):
            if self._cancel_event.is_set():
                raise CancelledError()
            base_cb(msg, frac)
        return wrapped

    def continue_with(self, segments: list[Segment], translations: list[str]) -> None:
        """用户在预览中编辑后继续(传回最终 segments 与 translations)"""
        self._final_segments = segments
        self._final_translations = translations
        self._user_continue = True

    # ------- QThread 入口 -------

    def run(self) -> None:
        try:
            self._run_pipeline()
        except CancelledError:
            self.log.emit("✗ 已取消")
            self.cancelled.emit()
        except Exception as e:
            # 如果是被取消导致的下游异常,按取消处理
            if self._cancel_event.is_set():
                self.log.emit("✗ 已取消")
                self.cancelled.emit()
            else:
                traceback.print_exc()
                self.failed.emit(str(e))
        finally:
            if self._tmp_audio and Path(self._tmp_audio).exists():
                try:
                    os.unlink(self._tmp_audio)
                except OSError:
                    pass

    # ------- 主流程 -------

    def _run_pipeline(self) -> None:
        video = self.video_path
        video_name = Path(video).stem

        # 0. 计算视频 ID(基于内容,用作缓存键)
        try:
            video_id = cache_mod.compute_video_id(video)
            self.log.emit(f"视频 ID: {video_id}  (缓存目录: ~/.subtitle_translator/cache/{video_id})")
        except Exception as e:
            video_id = ""
            self.log.emit(f"⚠ 无法计算视频 ID ({e}),本次不使用缓存")

        # 1. 检查 ASR 缓存
        asr_fp = cache_mod.asr_fingerprint(self.config, self.source_language)
        segments: list[Segment] = []
        detected_lang: str = ""
        cached_asr = cache_mod.load_asr_result(video_id, asr_fp) if video_id else None

        if cached_asr:
            segments, detected_lang = cached_asr
            self.log.emit(f"✓ 命中 ASR 缓存:跳过语音识别 ({len(segments)} 段,语种 {detected_lang})")
            self.stage_changed.emit("已从缓存恢复 ASR 结果")
            self.progress.emit(50)
        else:
            self._check_cancelled()
            # 1a. 提取音频
            self.stage_changed.emit("提取音频")
            self.log.emit(f"开始处理: {video}")
            self._tmp_audio = video_utils.extract_audio(
                video, progress_cb=lambda m: self.log.emit(m)
            )
            self.progress.emit(10)
            self._check_cancelled()

            # 1b. ASR — 包装回调,每次进度更新都会触发 cancel 检查
            self.stage_changed.emit("语音识别")
            transcriber = build_transcriber(self.config)
            segments, detected_lang = transcriber.transcribe(
                self._tmp_audio,
                source_language=self.source_language,
                progress_cb=self._wrap_progress_cb(lambda msg, frac: (
                    self.log.emit(msg),
                    self.progress.emit(10 + int(frac * 40)),
                )),
            )
            self.log.emit(f"识别到 {len(segments)} 段,语种: {detected_lang}")
            if not segments:
                raise RuntimeError("未识别到任何字幕段落")

            # 1c. 保存 ASR 缓存(完成后立刻存,即使后续阶段崩溃也不会重跑)
            if video_id:
                try:
                    cache_mod.save_asr_result(video_id, asr_fp, segments, detected_lang)
                    self.log.emit("✓ ASR 结果已缓存,后续可秒级恢复")
                except Exception as e:
                    self.log.emit(f"⚠ 缓存 ASR 失败 (不影响主流程): {e}")

        self._check_cancelled()

        # 2. 可选:LLM 润色(也带缓存)
        if self.polish_original:
            polish_fp = cache_mod.polish_fingerprint(self.config, segments)
            cached_polish = cache_mod.load_polish_result(video_id, polish_fp) if video_id else None
            if cached_polish:
                segments = cached_polish
                self.log.emit("✓ 命中润色缓存:跳过 LLM 润色")
                self.stage_changed.emit("已从缓存恢复润色结果")
                self.progress.emit(65)
            else:
                self.stage_changed.emit("LLM 润色原文")
                self.log.emit("启用大模型润色: 仅修正标点/错字/幻觉,不改原意,不翻译")
                try:
                    polisher = build_translator(self.config)
                    polished_texts = polisher.polish_segments(
                        segments, language=detected_lang,
                        progress_cb=self._wrap_progress_cb(lambda msg, frac: (
                            self.log.emit(msg),
                            self.progress.emit(50 + int(frac * 15)),
                        )),
                    )
                    fixed = 0
                    for i, txt in enumerate(polished_texts):
                        if txt and txt.strip() and txt.strip() != segments[i].text.strip():
                            segments[i].text = txt.strip()
                            fixed += 1
                    self.log.emit(f"润色完成,共修正 {fixed}/{len(segments)} 段")
                    if video_id:
                        try:
                            cache_mod.save_polish_result(video_id, polish_fp, segments)
                            self.log.emit("✓ 润色结果已缓存")
                        except Exception as e:
                            self.log.emit(f"⚠ 缓存润色失败: {e}")
                except Exception as e:
                    self.log.emit(f"⚠ 润色失败,使用 Whisper 原文继续: {e}")

        # 3. 翻译(若需要)— 也带缓存
        need_translate = (
            self.target_language
            and detected_lang
            and not self._same_language(detected_lang, self.target_language)
        )
        requested_mode = self.subtitle_mode
        if requested_mode == "original":
            need_translate = False

        translations: list[str] = []
        if need_translate:
            trans_fp = cache_mod.translate_fingerprint(
                self.config, segments, detected_lang, self.target_language,
            )
            cached_trans = cache_mod.load_translate_result(video_id, trans_fp) if video_id else None
            if cached_trans and len(cached_trans) == len(segments):
                translations = cached_trans
                self.log.emit(f"✓ 命中翻译缓存:跳过 LLM 翻译 ({len(translations)} 条)")
                self.stage_changed.emit("已从缓存恢复翻译结果")
                self.progress.emit(80)
            else:
                self.stage_changed.emit("翻译字幕")
                translator = build_translator(self.config)
                translations = translator.translate_segments(
                    segments,
                    source_language=detected_lang,
                    target_language=self.target_language,
                    progress_cb=self._wrap_progress_cb(lambda msg, frac: (
                        self.log.emit(msg),
                        self.progress.emit(50 + int(frac * 30)),
                    )),
                )
                if video_id and translations:
                    try:
                        cache_mod.save_translate_result(video_id, trans_fp, translations)
                        self.log.emit("✓ 翻译结果已缓存")
                    except Exception as e:
                        self.log.emit(f"⚠ 缓存翻译失败: {e}")
        else:
            if requested_mode != "original":
                self.log.emit("源语言与目标语言相同,跳过翻译,自动切换为仅原文模式")
            translations = [s.text for s in segments]

        # 4. 写 SRT(初版,用户可后续编辑)
        self.stage_changed.emit("生成字幕文件")
        out_dir = Path(self.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # 实际写入模式:用户请求的模式 + 翻译可用性
        if not need_translate:
            mode = "original"   # 没翻译就只能输出原文
        else:
            mode = requested_mode   # translated 或 bilingual

        # 文件名按模式 + 语言代码区分
        # 命名规范(与 SRT 和烧录视频统一):
        #   仅原文:    video.<src>.srt / video.<src>.mp4         如 movie.en.mp4
        #   仅译文:    video.<tgt>.srt / video.<tgt>.mp4         如 movie.zh.mp4
        #   双语:      video.<src>-<tgt>.srt / video.<src>-<tgt>.mp4  如 movie.en-zh.mp4
        #   软字幕兜底: video.<src>-<tgt>.softsub.mp4
        suffix_map = {
            "original":   f"{self.source_language if self.source_language != 'auto' else detected_lang}",
            "translated": f"{self.target_language}",
            "bilingual":  f"{detected_lang}-{self.target_language}",
        }
        self._lang_suffix = suffix_map.get(mode, self.target_language)   # 保存供烧录复用
        lang_suffix = self._lang_suffix
        srt_filename = f"{video_name}.{lang_suffix}.srt"
        self._srt_path = str(out_dir / srt_filename)
        write_srt(self._srt_path, segments, translations, mode=mode)
        self.log.emit(f"SRT 已生成: {self._srt_path}")
        self.progress.emit(85)

        # 5. 预览(可选)— 通过信号告诉 GUI,等待 continue_with 被调用
        if self.preview_before_burn:
            self.stage_changed.emit("等待用户预览/编辑")
            self.ready_for_preview.emit(self._srt_path, segments, translations)
            # 等待用户在预览窗里 保存 / 取消
            while not self._user_continue:
                self.msleep(100)
                # 兜底:用户从主面板点取消也会触发
                if self._cancel_event.is_set():
                    raise CancelledError()
            # 用户在预览窗点取消 → cancel() 把 _user_cancel 设 True
            # 必须 raise CancelledError 而不是 return,否则 run() 不会发 cancelled 信号
            # 主面板 UI 就一直卡在 85% 不重置
            if self._user_cancel:
                raise CancelledError()
            # 使用用户编辑后的内容重新写一遍
            segments = self._final_segments or segments
            translations = self._final_translations or translations
            write_srt(self._srt_path, segments, translations, mode=mode)
            self.log.emit("已保存用户编辑后的字幕")

        # 6. 烧录(三级降级:libass → drawtext → softmux)
        burned_path = ""
        if self.burn:
            ext = Path(video).suffix or ".mp4"
            # 命名:与 SRT 对齐,方便目录里按字母排序看到配对
            #   video.en-zh.srt   <─ 字幕文件
            #   video.en-zh.mp4   <─ 烧录后视频
            burned_path = str(out_dir / f"{video_name}.{self._lang_suffix}{ext}")
            has_libass = video_utils.check_filter_available("subtitles")

            # 烧录回调:写日志的同时把烧录百分比映射到主进度条 (85→100)
            import re as _re
            def _burn_cb(m: str):
                self.log.emit(m)
                mo = _re.search(r"烧录进度:\s*(\d+)%", m)
                if mo:
                    pct = int(mo.group(1))
                    self.progress.emit(85 + int(pct * 0.15))

            if has_libass:
                # 🥇 最佳:libass 渲染硬字幕(ASS 样式,描边/字体最专业)
                self.stage_changed.emit("烧录字幕到视频")
                self.progress.emit(85)
                video_utils.burn_subtitle(
                    video_path=video,
                    subtitle_path=self._srt_path,
                    output_path=burned_path,
                    font_name=self.config.get("subtitle_font", "Arial"),
                    font_size=int(self.config.get("subtitle_font_size", 22)),
                    primary_color=self.config.get("subtitle_font_color", "&Hffffff"),
                    outline_color=self.config.get("subtitle_outline_color", "&H000000"),
                    position=self.config.get("subtitle_position", "bottom"),
                    progress_cb=_burn_cb,
                )
                self.log.emit(f"烧录完成 (libass): {burned_path}")
            else:
                # 🥈 兜底 1:drawtext 渲染硬字幕(不需要 libass,任何 ffmpeg 都行)
                cjk_font = video_utils.find_cjk_font()
                if cjk_font:
                    self.stage_changed.emit("烧录字幕 (drawtext,无 libass)")
                    self.progress.emit(85)
                    self.log.emit(
                        "⚠ FFmpeg 缺 libass,改用 drawtext 烧硬字幕。"
                        "效果略简陋(无 ASS 样式),但视频里字幕永远可见。"
                    )
                    try:
                        video_utils.burn_subtitle_drawtext(
                            video_path=video,
                            subtitle_path=self._srt_path,
                            output_path=burned_path,
                            font_size=int(self.config.get("subtitle_font_size", 22)),
                            font_color="white",
                            outline_color="black",
                            position=self.config.get("subtitle_position", "bottom"),
                            progress_cb=_burn_cb,
                        )
                        self.log.emit(f"烧录完成 (drawtext): {burned_path}")
                    except Exception as e:
                        self.log.emit(f"⚠ drawtext 烧录失败: {e},改为软字幕嵌入")
                        burned_path = self._do_softmux(out_dir, video_name, ext, video)
                else:
                    # 🥉 终极兜底:连中文字体都找不到,只能软字幕嵌入
                    self.log.emit("⚠ 找不到中文字体,无法用 drawtext。改为软字幕嵌入。")
                    burned_path = self._do_softmux(out_dir, video_name, ext, video)

        self.progress.emit(100)
        self.stage_changed.emit("完成")
        self.finished_ok.emit(self._srt_path, burned_path)

    def _do_softmux(self, out_dir: Path, video_name: str, ext: str, video: str) -> str:
        """软字幕兜底:不重新编码,秒级嵌入到 mp4 字幕轨。
        命名:video.<langs>.softsub.mp4(加 softsub 后缀以区别硬字幕版本)"""
        self.stage_changed.emit("嵌入软字幕 (FFmpeg 无 libass)")
        lang = getattr(self, "_lang_suffix", self.target_language)
        softsub_path = str(out_dir / f"{video_name}.{lang}.softsub{ext}")
        video_utils.mux_subtitle(
            video_path=video,
            subtitle_path=self._srt_path,
            output_path=softsub_path,
            language=self.target_language,
            progress_cb=lambda m: self.log.emit(m),
        )
        self.log.emit(f"软字幕嵌入完成: {softsub_path}")
        self.log.emit("  播放时:用 IINA / VLC 自动显示,QuickTime 在'显示→字幕'里手动开启")
        return softsub_path

    @staticmethod
    def _same_language(a: str, b: str) -> bool:
        """简单判断两个语种代码是否等同(zh / zh-cn / zh-tw 不同)"""
        if not a or not b:
            return False
        a = a.lower().replace("_", "-")
        b = b.lower().replace("_", "-")
        if a == b:
            return True
        # zh 与 zh-cn 视为相同
        zh_variants = {"zh", "zh-cn", "zh-hans"}
        if a in zh_variants and b in zh_variants:
            return True
        return False
