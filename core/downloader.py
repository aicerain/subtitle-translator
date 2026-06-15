"""
在线视频下载封装。

用 yt-dlp 统一支持 YouTube、Bilibili、TikTok、抖音等站点。
下载结果作为普通本地视频交给现有字幕生成流水线继续处理。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse


ProgressCb = Optional[Callable[[str], None]]


class DownloadError(RuntimeError):
    """URL 视频下载失败。"""


@dataclass
class DownloadResult:
    path: str
    title: str = ""
    video_id: str = ""


def is_video_url(value: str) -> bool:
    """仅接受 http/https URL。具体站点支持范围交给 yt-dlp 判断。"""
    if not value:
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def download_video_from_url(
    url: str,
    output_dir: str,
    progress_cb: ProgressCb = None,
    ydl_cls=None,
) -> DownloadResult:
    """下载 URL 视频到 output_dir,返回最终文件路径。"""
    if not is_video_url(url):
        raise DownloadError("请输入有效的视频 URL (http/https)")

    out_dir = Path(output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    if ydl_cls is None:
        try:
            from yt_dlp import YoutubeDL
            ydl_cls = YoutubeDL
        except ImportError as e:
            raise DownloadError("未安装 yt-dlp。请运行: pip install -r requirements.txt") from e

    def _hook(status: dict) -> None:
        if progress_cb is None:
            return
        state = status.get("status")
        if state == "downloading":
            total = status.get("total_bytes") or status.get("total_bytes_estimate") or 0
            done = status.get("downloaded_bytes") or 0
            if total:
                pct = int(min(100, max(0, done / total * 100)))
                progress_cb(f"下载进度: {pct}%")
            else:
                progress_cb("下载中...")
        elif state == "finished":
            filename = Path(status.get("filename") or "").name
            progress_cb(f"下载完成: {filename}" if filename else "下载完成")

    options = {
        "paths": {"home": str(out_dir)},
        "outtmpl": "%(title).200B [%(id)s].%(ext)s",
        "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
        "merge_output_format": "mp4",
        "restrictfilenames": False,
        "windowsfilenames": True,
        "noplaylist": True,
        "progress_hooks": [_hook],
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with ydl_cls(options) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as e:
        raise DownloadError(_format_download_error(e)) from e

    path = _resolve_downloaded_path(info, out_dir)
    if not path:
        raise DownloadError("视频已下载,但无法定位下载后的文件路径")

    return DownloadResult(
        path=str(path),
        title=str(info.get("title") or path.stem),
        video_id=str(info.get("id") or ""),
    )


def _resolve_downloaded_path(info: dict, output_dir: Path) -> Optional[Path]:
    """从 yt-dlp 返回信息里找最终文件路径。"""
    for item in info.get("requested_downloads") or []:
        filepath = item.get("filepath") or item.get("filename")
        if filepath:
            return Path(filepath)

    filepath = info.get("filepath") or info.get("_filename") or info.get("filename")
    if filepath:
        return Path(filepath)

    title = info.get("title")
    video_id = info.get("id")
    ext = info.get("ext") or "mp4"
    if title and video_id:
        candidate = output_dir / f"{title} [{video_id}].{ext}"
        return candidate
    return None


def _format_download_error(err: Exception) -> str:
    msg = str(err).strip()
    if not msg:
        return "视频下载失败"
    return f"视频下载失败: {msg}"
