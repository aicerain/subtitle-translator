"""
视频处理模块 - 封装 FFmpeg 调用
负责:
1. 从视频中提取音频(用于喂给语音识别)
2. 将字幕烧录(硬字幕)到视频中
3. 检测 FFmpeg 是否可用
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Optional


def find_ffmpeg() -> Optional[str]:
    """查找系统中的 ffmpeg 可执行文件路径"""
    # 优先环境变量
    env_path = os.environ.get("FFMPEG_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    # PATH 中查找
    found = shutil.which("ffmpeg")
    if found:
        return found

    # macOS 常见安装路径
    common_paths = [
        "/usr/local/bin/ffmpeg",
        "/opt/homebrew/bin/ffmpeg",
        "/usr/bin/ffmpeg",
    ]
    for p in common_paths:
        if Path(p).exists():
            return p

    return None


def check_ffmpeg_installed() -> tuple[bool, str]:
    """检测 FFmpeg 是否安装,返回 (是否可用, 版本信息或错误提示)"""
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return False, "未找到 FFmpeg。请先安装:\n  macOS: brew install ffmpeg\n  Windows: 下载 https://ffmpeg.org/download.html\n  Linux: apt install ffmpeg"
    try:
        result = subprocess.run(
            [ffmpeg, "-version"],
            capture_output=True, text=True, timeout=10
        )
        first_line = result.stdout.splitlines()[0] if result.stdout else ""
        return True, first_line
    except Exception as e:
        return False, f"FFmpeg 调用失败: {e}"


def extract_audio(
    video_path: str,
    output_audio_path: Optional[str] = None,
    sample_rate: int = 16000,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> str:
    """
    从视频提取单声道 WAV 音频(16kHz 是 Whisper 标准输入)。
    返回输出音频路径。
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("FFmpeg 未安装")

    if output_audio_path is None:
        fd, output_audio_path = tempfile.mkstemp(suffix=".wav", prefix="subtitle_audio_")
        os.close(fd)

    cmd = [
        ffmpeg, "-y", "-i", video_path,
        "-vn",                         # 不要视频
        "-acodec", "pcm_s16le",        # 16-bit PCM
        "-ar", str(sample_rate),
        "-ac", "1",                    # 单声道
        output_audio_path,
    ]
    if progress_cb:
        progress_cb(f"提取音频: {Path(video_path).name}")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"音频提取失败:\n{proc.stderr[-2000:]}")
    return output_audio_path


def get_video_duration(video_path: str) -> float:
    """获取视频时长(秒)"""
    info = probe_video(video_path)
    return info.get("duration", 0.0)


def probe_video(video_path: str) -> dict:
    """
    探测视频元信息。返回字典:
      duration: float    总时长(秒)
      width: int
      height: int
      codec: str         视频编码
      audio_codec: str
      bitrate: int       总码率 (bps)
      fps: float
    解析失败的字段为 0/空。
    """
    info = {
        "duration": 0.0, "width": 0, "height": 0,
        "codec": "", "audio_codec": "", "bitrate": 0, "fps": 0.0,
    }
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return info
    proc = subprocess.run(
        [ffmpeg, "-i", video_path], capture_output=True, text=True, timeout=15,
    )
    output = proc.stderr or ""

    import re
    # Duration
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", output)
    if m:
        h, mn, s = m.groups()
        info["duration"] = int(h) * 3600 + int(mn) * 60 + float(s)
    # bitrate (总码率)
    m = re.search(r"bitrate:\s*(\d+)\s*kb/s", output)
    if m:
        info["bitrate"] = int(m.group(1)) * 1000
    # 视频流: "Stream #0:0... Video: h264 ... 1920x1080 ... 30 fps"
    m = re.search(
        r"Stream #\d+:\d+.*?Video:\s*([\w]+).*?(\d{2,5})x(\d{2,5})", output
    )
    if m:
        info["codec"] = m.group(1)
        info["width"] = int(m.group(2))
        info["height"] = int(m.group(3))
    m_fps = re.search(r"(\d+(?:\.\d+)?)\s*fps", output)
    if m_fps:
        try:
            info["fps"] = float(m_fps.group(1))
        except ValueError:
            pass
    # 音频流
    m = re.search(r"Stream #\d+:\d+.*?Audio:\s*([\w]+)", output)
    if m:
        info["audio_codec"] = m.group(1)
    return info


def human_size(num_bytes: int) -> str:
    """字节数 → 人类可读 (12.3 MB)"""
    if num_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(num_bytes)
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    if i == 0:
        return f"{int(size)} {units[i]}"
    return f"{size:.1f} {units[i]}"


def extract_frame(
    video_path: str,
    time_seconds: float,
    output_path: str,
    max_width: int = 480,
    timeout: int = 8,
) -> str:
    """
    从视频指定时间点提取一帧画面。
    用 -ss 在 -i 之前实现快速 seek(关键帧级,误差最多 ~2 秒,够预览用)。

    Args:
        video_path: 源视频
        time_seconds: 提取时间点(秒)
        output_path: 输出 JPG 路径
        max_width: 缩放宽度(高度按比例),默认 480
        timeout: ffmpeg 超时秒数

    Returns:
        output_path
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("FFmpeg 未安装")

    # 时间点 clamp 到 >= 0
    t = max(0.0, float(time_seconds))

    cmd = [
        ffmpeg, "-y",
        "-ss", f"{t:.3f}",              # -ss 在 -i 之前 = 快速 seek
        "-i", video_path,
        "-frames:v", "1",                # 只导一帧
        "-vf", f"scale='min({max_width},iw)':-2",  # 等比缩放,宽不超过 max_width
        "-q:v", "3",                     # 质量(2=最高, 31=最低)
        "-an",                            # 不要音频
        "-sn",                            # 不要字幕
        output_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        # 兜底:有些奇怪格式 -ss 在 -i 前会卡住,改成在后面
        cmd2 = [
            ffmpeg, "-y",
            "-i", video_path,
            "-ss", f"{t:.3f}",
            "-frames:v", "1",
            "-vf", f"scale='min({max_width},iw)':-2",
            "-q:v", "3", "-an", "-sn",
            output_path,
        ]
        proc = subprocess.run(cmd2, capture_output=True, timeout=timeout)
        if proc.returncode != 0:
            raise RuntimeError(
                f"关键帧提取失败 (t={t}s): {proc.stderr.decode('utf-8', errors='ignore')[-500:]}"
            )
    return output_path


def human_duration(seconds: float) -> str:
    """秒数 → 人类可读 (1h 23m 45s)"""
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m:02d}m {s:02d}s"
    if m > 0:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def _run_ffmpeg_with_progress(
    cmd: list[str],
    duration: float,
    progress_cb: Optional[Callable[[str], None]] = None,
    heartbeat_seconds: int = 30,
) -> None:
    """
    跑 ffmpeg,带 3 项防御:
      1. 单独线程排空 stderr,避免 64KB pipe 填满死锁
      2. 单独线程心跳,每 N 秒提示一次"仍在处理",即使 progress 不变
      3. 百分比去重(只在 pct 变化时打日志)
    失败时抛 RuntimeError,异常消息含 stderr 末尾几行。
    """
    import threading
    import time as _time

    proc = subprocess.Popen(
        cmd + ["-progress", "pipe:1", "-nostats"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )
    assert proc.stdout is not None and proc.stderr is not None

    # 1) stderr 排空线程 — 保留最后 200 行用于异常诊断
    stderr_tail: list[str] = []
    def _drain_stderr():
        for line in proc.stderr:
            stderr_tail.append(line.rstrip())
            if len(stderr_tail) > 200:
                stderr_tail.pop(0)
    stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
    stderr_thread.start()

    # 2) 心跳线程 — 长时间无进度更新时不让用户以为程序卡死
    last_update_time = [_time.time()]
    last_pct_for_hb = [0]
    stop_hb = threading.Event()
    def _heartbeat():
        while not stop_hb.is_set():
            _time.sleep(5)
            elapsed_silence = _time.time() - last_update_time[0]
            if elapsed_silence > heartbeat_seconds and progress_cb:
                progress_cb(
                    f"⏳ 仍在处理(已 {int(elapsed_silence)}s 无新进度,"
                    f"当前 {last_pct_for_hb[0]}%,大量字幕的 drawtext 烧录会很慢)"
                )
                last_update_time[0] = _time.time()   # 防止刷屏
    heartbeat_thread = threading.Thread(target=_heartbeat, daemon=True)
    heartbeat_thread.start()

    # 3) 读 stdout 抓进度,百分比变化才回调
    last_pct = -1
    try:
        for line in proc.stdout:
            line = line.strip()
            if line.startswith("out_time_ms=") and duration > 0 and progress_cb:
                try:
                    ms = int(line.split("=", 1)[1])
                    cur = ms / 1_000_000
                    pct = min(100, int(cur / duration * 100))
                    if pct != last_pct:
                        progress_cb(f"烧录进度: {pct}%")
                        last_pct = pct
                        last_pct_for_hb[0] = pct
                        last_update_time[0] = _time.time()
                except ValueError:
                    pass
    finally:
        stop_hb.set()

    proc.wait()
    stderr_thread.join(timeout=2.0)

    if proc.returncode != 0:
        tail = "\n".join(stderr_tail[-30:])
        raise RuntimeError(f"ffmpeg 失败 (exit {proc.returncode}):\n{tail[-2000:]}")


def check_filter_available(filter_name: str) -> bool:
    """检查 ffmpeg 是否带某个 filter(subtitles 需要 libass)"""
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return False
    try:
        proc = subprocess.run(
            [ffmpeg, "-hide_banner", "-filters"],
            capture_output=True, text=True, timeout=10,
        )
        for line in proc.stdout.splitlines():
            # ffmpeg -filters 输出格式: ".. T.. subtitles  V->V  ..."
            parts = line.strip().split()
            if len(parts) >= 2 and parts[1] == filter_name:
                return True
        return False
    except Exception:
        return False


def check_encoder_available(encoder_name: str) -> bool:
    """检查 ffmpeg 是否有某个编码器(h264_videotoolbox / hevc_videotoolbox / h264_nvenc 等)"""
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return False
    try:
        proc = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=10,
        )
        return encoder_name in proc.stdout
    except Exception:
        return False


def get_video_encode_args(prefer_hw: bool = True) -> tuple[list[str], str]:
    """
    返回视频编码器参数列表 + 用于日志的描述。
    优先级:
      1. macOS h264_videotoolbox  (Apple Silicon / Intel Mac 硬件编码,快 5-10x)
      2. NVIDIA h264_nvenc        (Linux/Windows NVIDIA GPU)
      3. libx264 medium crf=20    (软件兜底,任何机器都行)
    """
    if prefer_hw:
        if check_encoder_available("h264_videotoolbox"):
            # videotoolbox 用 -q:v (1-100, 越高越好) 或 -b:v 控制
            return (
                ["-c:v", "h264_videotoolbox",
                 "-q:v", "60",                    # 视觉质量约对应 crf=20
                 "-allow_sw", "1"],               # 硬件忙时回退软件
                "h264_videotoolbox (Mac 硬件加速)",
            )
        if check_encoder_available("h264_nvenc"):
            return (
                ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23"],
                "h264_nvenc (NVIDIA 硬件加速)",
            )
    return (
        ["-c:v", "libx264", "-preset", "medium", "-crf", "20"],
        "libx264 medium (软件编码,较慢)",
    )


LIBASS_INSTALL_HINT = (
    "你的 FFmpeg 缺少 libass(字幕渲染)支持,无法烧录硬字幕。\n\n"
    "▶ 解决办法:重装一个带 libass 的 FFmpeg\n\n"
    "  brew install libass\n"
    "  brew uninstall ffmpeg\n"
    "  brew install ffmpeg\n\n"
    "或用社区版本(默认带全部功能):\n"
    "  brew tap homebrew-ffmpeg/ffmpeg\n"
    "  brew uninstall ffmpeg\n"
    "  brew install homebrew-ffmpeg/ffmpeg/ffmpeg\n\n"
    "重装完成后再回来烧录。"
)


def find_cjk_font() -> Optional[str]:
    """找一个支持中文渲染的 TrueType 字体文件(给 drawtext 用)"""
    candidates = [
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/Library/Fonts/Arial Unicode MS.ttf",
        # Linux
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        # Windows
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    for p in candidates:
        if Path(p).exists():
            return p
    return None


def _escape_drawtext_value(text: str) -> str:
    """对 drawtext 的 text='...' 值做转义。
    规则:
      - \\\\ → 字面 \\
      - ' → \\' (单引号需要转义,因为我们用 ' 包裹值)
    其他字符在 ' 包裹内都是字面值。
    """
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\\'")
    return text


def burn_subtitle_drawtext(
    video_path: str,
    subtitle_path: str,
    output_path: str,
    font_size: int = 22,
    font_color: str = "white",
    outline_color: str = "black",
    position: str = "bottom",
    progress_cb: Optional[Callable[[str], None]] = None,
) -> str:
    """
    用 drawtext filter 烧录硬字幕 — **不依赖 libass**。
    任何 ffmpeg 默认都自带 drawtext,所以兼容性极强。

    适用场景:
      - 系统 ffmpeg 是阉割版,没 libass
      - 仍想要硬字幕(画在画面上,任何播放器都看得到)
    """
    from .srt_io import parse_srt

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("FFmpeg 未安装")
    font_file = find_cjk_font()
    if not font_file:
        raise RuntimeError(
            "找不到支持中文的字体,无法用 drawtext 烧硬字幕。\n"
            "macOS: 安装 PingFang 或类似中文字体到 /System/Library/Fonts/\n"
            "Linux: apt install fonts-noto-cjk"
        )

    segments = parse_srt(subtitle_path)
    if not segments:
        raise RuntimeError("字幕文件为空,无内容可烧")

    # 位置基线 (从下/上边的像素数)
    bottom_margin = 36

    # 构建 drawtext 链 — 每条字幕生成 1~2 个 drawtext (双语 = 2 行)
    line_height = font_size + 8
    filters: list[str] = []
    for seg in segments:
        text = (seg.text or "").strip()
        if not text:
            continue
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        n = len(lines)
        for i, line in enumerate(lines):
            esc = _escape_drawtext_value(line)
            # 从底部向上数: 最后一行(i=n-1)最靠近底部
            offset = bottom_margin + (n - 1 - i) * line_height
            if position == "top":
                y_expr = f"{offset}"
            elif position == "middle":
                y_expr = f"(h-text_h)/2-{(n - 1 - i) * line_height}"
            else:
                y_expr = f"h-text_h-{offset}"

            f = (
                f"drawtext=fontfile='{font_file}'"
                f":text='{esc}'"
                f":fontsize={font_size}"
                f":fontcolor={font_color}"
                f":bordercolor={outline_color}"
                f":borderw=2"
                f":x=(w-text_w)/2"
                f":y={y_expr}"
                f":enable='between(t\\,{seg.start:.3f}\\,{seg.end:.3f})'"
            )
            filters.append(f)

    if not filters:
        raise RuntimeError("解析后没有可烧录的字幕段")

    # 因为 filter 链可能很长(1000 段 × 2 行 → 200KB+),
    # 用 filter_complex_script 文件传,避免命令行长度限制
    fd, script_path = tempfile.mkstemp(suffix=".txt", prefix="burn_filter_")
    os.close(fd)
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(",".join(filters))

    try:
        # 选编码器:优先硬件加速,极大降低 drawtext 计算密集场景的耗时
        encode_args, enc_desc = get_video_encode_args(prefer_hw=True)
        cmd = [
            ffmpeg, "-y", "-i", video_path,
            "-filter_complex_script", script_path,
            "-c:a", "copy",
            *encode_args,
            output_path,
        ]
        if progress_cb:
            progress_cb(
                f"用 drawtext 烧录硬字幕 ({len(filters)} 条文本片段),"
                f"编码: {enc_desc}"
            )

        duration = get_video_duration(video_path)
        # drawtext 1000+ filter 极慢,把心跳超时延长到 60s 避免误报
        _run_ffmpeg_with_progress(cmd, duration, progress_cb, heartbeat_seconds=60)

        if progress_cb:
            progress_cb("烧录完成 ✓")
        return output_path
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


def mux_subtitle(
    video_path: str,
    subtitle_path: str,
    output_path: str,
    language: str = "und",
    progress_cb: Optional[Callable[[str], None]] = None,
) -> str:
    """
    把字幕作为"软字幕"(可在播放器开关)mux 进 mp4。
    优点:不需要 libass,不重新编码视频(秒级完成)。
    缺点:不是硬字幕,有些播放器默认不显示,需要手动开。
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("FFmpeg 未安装")

    cmd = [
        ffmpeg, "-y",
        "-i", video_path,
        "-i", subtitle_path,
        "-map", "0:v", "-map", "0:a?", "-map", "1",
        "-c:v", "copy", "-c:a", "copy",
        "-c:s", "mov_text",                       # mp4 内嵌字幕标准
        "-metadata:s:s:0", f"language={language}",
        "-disposition:s:0", "default",            # 默认开启字幕显示
        output_path,
    ]
    if progress_cb:
        progress_cb("开始嵌入软字幕(秒级,不重新编码)...")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"软字幕嵌入失败:\n{proc.stderr[-2000:]}")
    if progress_cb:
        progress_cb("软字幕嵌入完成 ✓")
    return output_path


def burn_subtitle(
    video_path: str,
    subtitle_path: str,
    output_path: str,
    font_name: str = "Arial",
    font_size: int = 22,
    primary_color: str = "&Hffffff",
    outline_color: str = "&H000000",
    position: str = "bottom",
    progress_cb: Optional[Callable[[str], None]] = None,
) -> str:
    """
    将字幕硬烧录到视频中。subtitle_path 可以是 .srt 或 .ass 文件。

    实现细节:
      - SRT 先 copy 到 /tmp 用一个无特殊字符的临时文件名,避免源文件路径里
        诸如 `r2---sn.googlevide.en-zh.srt` 之类被 ffmpeg 8.x 的 filter
        parser 误解析为 key=value(报 "No option name near" 错误)。
      - 用 subtitles=filename='...':force_style='...' 命名参数语法,
        比位置参数稳定得多。
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("FFmpeg 未安装")

    # 烧录硬字幕必须有 libass(subtitles filter)。提前检测,避免跑完才报错。
    if not check_filter_available("subtitles"):
        raise RuntimeError(LIBASS_INSTALL_HINT)

    # 1. 把字幕 copy 到 /tmp 用极简文件名,完全绕开命名带来的 filter 解析问题
    import shutil as _shutil
    fd, safe_srt = tempfile.mkstemp(suffix=".srt", prefix="burn_")
    os.close(fd)
    _shutil.copy(subtitle_path, safe_srt)

    try:
        # 即便 /tmp 路径无特殊字符,Windows 上 C: 这种冒号仍需转义给 filter parser
        # macOS/Linux 上一般 noop
        sub_path_for_filter = safe_srt.replace("\\", "/").replace(":", "\\:")

        # ASS Alignment: 1-3=底部, 4-6=中部, 7-9=顶部
        alignment_map = {"bottom": 2, "middle": 5, "top": 8}
        alignment = alignment_map.get(position, 2)

        style_parts = [
            f"FontName={font_name}",
            f"FontSize={font_size}",
            f"PrimaryColour={primary_color}",
            f"OutlineColour={outline_color}",
            f"Alignment={alignment}",
            "Outline=2",
            "Shadow=0",
            "BorderStyle=1",
        ]
        force_style = ",".join(style_parts)

        # 关键:用 filename= 命名参数,而不是位置参数
        # 新版 ffmpeg 对位置参数的字符串解析很严苛
        vf = f"subtitles=filename='{sub_path_for_filter}':force_style='{force_style}'"

        # 选编码器:优先硬件加速
        encode_args, enc_desc = get_video_encode_args(prefer_hw=True)
        cmd = [
            ffmpeg, "-y", "-i", video_path,
            "-vf", vf,
            "-c:a", "copy",
            *encode_args,
            output_path,
        ]

        if progress_cb:
            progress_cb(f"开始烧录字幕到视频 (编码: {enc_desc})...")

        duration = get_video_duration(video_path)
        _run_ffmpeg_with_progress(cmd, duration, progress_cb)

        if progress_cb:
            progress_cb("烧录完成 ✓")
        return output_path
    finally:
        # 总是清理临时 SRT
        try:
            if Path(safe_srt).exists():
                os.unlink(safe_srt)
        except OSError:
            pass
