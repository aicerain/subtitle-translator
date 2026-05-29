"""
字幕生成模块 - 把 (Segment + 译文) 写成标准 .srt 文件。
支持:
- 仅原文
- 仅译文
- 双语(原文 + 译文,两行)
"""
from __future__ import annotations
from pathlib import Path
from typing import Literal

from .transcriber import Segment


SubtitleMode = Literal["original", "translated", "bilingual"]


def format_srt_time(seconds: float) -> str:
    """秒数 → SRT 时间格式 HH:MM:SS,mmm"""
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000:
        s += 1
        ms -= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(
    output_path: str,
    segments: list[Segment],
    translations: list[str] | None = None,
    mode: SubtitleMode = "translated",
) -> str:
    """
    把字幕段落写入 SRT 文件。
    - mode = "original"   : 仅原语言
    - mode = "translated" : 仅目标语言(必须传 translations)
    - mode = "bilingual"  : 双字幕 — 原文在上,译文在下
    """
    if mode != "original" and translations is None:
        raise ValueError("mode != 'original' 时必须传 translations")
    if translations is not None and len(translations) != len(segments):
        raise ValueError("translations 与 segments 长度不一致")

    lines: list[str] = []
    index = 1
    for i, seg in enumerate(segments):
        text_original = (seg.text or "").strip()
        if not text_original and (translations is None or not (translations[i] or "").strip()):
            continue

        # 防止 end <= start
        start = seg.start
        end = seg.end if seg.end > seg.start else seg.start + 1.0

        if mode == "original":
            body = text_original
        elif mode == "translated":
            body = (translations[i] or "").strip() or text_original
        else:  # bilingual — 原文在上,译文在下
            tr = (translations[i] or "").strip() if translations else ""
            if tr and text_original and tr != text_original:
                body = f"{text_original}\n{tr}"
            else:
                body = text_original or tr

        lines.append(str(index))
        lines.append(f"{format_srt_time(start)} --> {format_srt_time(end)}")
        lines.append(body)
        lines.append("")
        index += 1

    output_path = str(output_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return output_path
