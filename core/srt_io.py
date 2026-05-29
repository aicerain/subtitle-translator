"""SRT 解析 - 用于在预览/编辑后重新加载字幕"""
from __future__ import annotations
import re
from pathlib import Path

from .transcriber import Segment


def parse_srt_time(s: str) -> float:
    """SRT 时间 HH:MM:SS,mmm → 秒"""
    s = s.strip().replace(".", ",")
    m = re.match(r"(\d+):(\d+):(\d+),(\d+)", s)
    if not m:
        return 0.0
    h, mn, sec, ms = m.groups()
    return int(h) * 3600 + int(mn) * 60 + int(sec) + int(ms) / 1000.0


def parse_srt(srt_path: str) -> list[Segment]:
    """读取 SRT 文件 → Segment 列表(text 用 \\n 连接多行)"""
    text = Path(srt_path).read_text(encoding="utf-8")
    # 按空行分块
    blocks = re.split(r"\n\s*\n", text.strip())
    segments: list[Segment] = []
    for block in blocks:
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        # 第 0 行可能是序号,第 1 行是时间,其余是字幕文本
        time_line_idx = 0
        if "-->" not in lines[0]:
            time_line_idx = 1
        if time_line_idx >= len(lines) or "-->" not in lines[time_line_idx]:
            continue
        try:
            start_s, end_s = lines[time_line_idx].split("-->")
            start = parse_srt_time(start_s)
            end = parse_srt_time(end_s)
        except ValueError:
            continue
        body = "\n".join(lines[time_line_idx + 1:]).strip()
        segments.append(Segment(start=start, end=end, text=body))
    return segments
