"""
阶段性缓存 — 让重启/崩溃后能跳过已完成的昂贵阶段。

缓存目录:~/.subtitle_translator/cache/<video_id>/
每个阶段一个 JSON 文件,带 fingerprint 字段,配置变了自动失效。

阶段缓存文件:
  asr.json     — Whisper 识别结果 (最贵,可省 10-100 分钟)
  polish.json  — LLM 原文润色结果
  translate.json — LLM 翻译结果

每个文件结构:
{
  "fingerprint": {...相关配置项...},
  "data": {...},
  "cached_at": "ISO 时间戳",
  "version": 1
}
"""
from __future__ import annotations
import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .transcriber import Segment


CACHE_VERSION = 1
CACHE_ROOT = Path.home() / ".subtitle_translator" / "cache"


# ============================================================
# Video ID 计算 — 让缓存能在文件移动/重命名后仍命中
# ============================================================

def compute_video_id(video_path: str) -> str:
    """
    生成视频的稳定 ID:基于文件大小 + 前后 1MB 内容的 sha256。
    这样即使文件被移动或重命名,只要内容一样就命中同一缓存。
    """
    p = Path(video_path)
    if not p.exists():
        raise FileNotFoundError(video_path)
    size = p.stat().st_size
    h = hashlib.sha256()
    h.update(str(size).encode())
    chunk = 1024 * 1024  # 1 MB
    with open(p, "rb") as f:
        h.update(f.read(chunk))
        if size > chunk * 2:
            f.seek(-chunk, os.SEEK_END)
            h.update(f.read(chunk))
    return h.hexdigest()[:16]   # 16 字符够避免碰撞


def cache_dir_for(video_id: str) -> Path:
    d = CACHE_ROOT / video_id
    d.mkdir(parents=True, exist_ok=True)
    return d


# ============================================================
# 通用 save / load
# ============================================================

def _save_stage(video_id: str, stage_name: str, payload: dict) -> None:
    payload = dict(payload)
    payload["cached_at"] = datetime.now().isoformat(timespec="seconds")
    payload["version"] = CACHE_VERSION
    path = cache_dir_for(video_id) / f"{stage_name}.json"
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    tmp.replace(path)   # 原子替换,避免半写状态


def _load_stage(video_id: str, stage_name: str) -> Optional[dict]:
    path = cache_dir_for(video_id) / f"{stage_name}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("version") != CACHE_VERSION:
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def _fingerprint_match(saved: dict, expected: dict) -> bool:
    """检查 saved fingerprint 是否与 expected 完全一致"""
    return saved == expected


def _segments_hash(segments: list[Segment]) -> str:
    """计算 segments 内容指纹 — 用于判断 ASR 输出变没变"""
    h = hashlib.sha256()
    for s in segments:
        h.update(f"{s.start:.3f}|{s.end:.3f}|{s.text}\n".encode("utf-8"))
    return h.hexdigest()[:16]


# ============================================================
# ASR 阶段缓存
# ============================================================

def asr_fingerprint(config: dict, source_language: str) -> dict:
    """ASR 命中条件:引擎、模型、计算精度、源语言都得一样。
    asr_postproc_version:后处理规则版本号,改了截断/合并逻辑就 bump 一次,
    让所有旧缓存自动失效。"""
    return {
        "asr_engine": config.get("asr_engine", "faster-whisper"),
        "whisper_model_size": config.get("whisper_model_size", "base"),
        "whisper_compute_type": config.get("whisper_compute_type", "auto"),
        "whisper_device": config.get("whisper_device", "auto"),
        "openai_whisper_model": config.get("openai_whisper_model", "whisper-1"),
        "source_language": source_language,
        "asr_postproc_version": 2,   # v2: 加了 condition_on_previous_text=False + 时长截断
    }


def save_asr_result(video_id: str, fingerprint: dict, segments: list[Segment],
                    detected_lang: str) -> None:
    _save_stage(video_id, "asr", {
        "fingerprint": fingerprint,
        "detected_lang": detected_lang,
        "segments": [
            {"start": s.start, "end": s.end, "text": s.text, "language": s.language}
            for s in segments
        ],
    })


def load_asr_result(video_id: str, fingerprint: dict) -> Optional[tuple[list[Segment], str]]:
    data = _load_stage(video_id, "asr")
    if not data or not _fingerprint_match(data.get("fingerprint", {}), fingerprint):
        return None
    segs = [
        Segment(
            start=s["start"], end=s["end"], text=s["text"],
            language=s.get("language", ""),
        )
        for s in data.get("segments", [])
    ]
    return segs, data.get("detected_lang", "")


# ============================================================
# Polish 阶段缓存
# ============================================================

def polish_fingerprint(config: dict, segments: list[Segment]) -> dict:
    """润色命中条件:翻译模型 + 源 segments 指纹一致"""
    provider = config.get("translator_provider", "openai")
    sub = config.get("translator_configs", {}).get(provider, {})
    return {
        "provider": provider,
        "model": sub.get("model", ""),
        "base_url": sub.get("base_url", ""),
        "segments_hash": _segments_hash(segments),
    }


def save_polish_result(video_id: str, fingerprint: dict,
                       polished_segments: list[Segment]) -> None:
    _save_stage(video_id, "polish", {
        "fingerprint": fingerprint,
        "polished": [
            {"start": s.start, "end": s.end, "text": s.text, "language": s.language}
            for s in polished_segments
        ],
    })


def load_polish_result(video_id: str, fingerprint: dict) -> Optional[list[Segment]]:
    data = _load_stage(video_id, "polish")
    if not data or not _fingerprint_match(data.get("fingerprint", {}), fingerprint):
        return None
    return [
        Segment(start=s["start"], end=s["end"], text=s["text"],
                language=s.get("language", ""))
        for s in data.get("polished", [])
    ]


# ============================================================
# Translate 阶段缓存
# ============================================================

def translate_fingerprint(config: dict, segments: list[Segment],
                          source_lang: str, target_lang: str) -> dict:
    """翻译命中条件:翻译模型 + 源 segments 指纹 + 目标语言一致"""
    provider = config.get("translator_provider", "openai")
    sub = config.get("translator_configs", {}).get(provider, {})
    return {
        "provider": provider,
        "model": sub.get("model", ""),
        "base_url": sub.get("base_url", ""),
        "source_lang": source_lang,
        "target_lang": target_lang,
        "segments_hash": _segments_hash(segments),
    }


def save_translate_result(video_id: str, fingerprint: dict,
                          translations: list[str]) -> None:
    _save_stage(video_id, "translate", {
        "fingerprint": fingerprint,
        "translations": translations,
    })


def load_translate_result(video_id: str, fingerprint: dict) -> Optional[list[str]]:
    data = _load_stage(video_id, "translate")
    if not data or not _fingerprint_match(data.get("fingerprint", {}), fingerprint):
        return None
    return data.get("translations", [])


# ============================================================
# 管理:列出 / 清理
# ============================================================

def list_cached_videos() -> list[dict]:
    """列出所有缓存的视频条目"""
    if not CACHE_ROOT.exists():
        return []
    out = []
    for d in CACHE_ROOT.iterdir():
        if not d.is_dir():
            continue
        entry = {"id": d.name, "path": str(d), "stages": [], "size": 0}
        for f in d.iterdir():
            if f.suffix == ".json":
                entry["stages"].append(f.stem)
                entry["size"] += f.stat().st_size
        out.append(entry)
    return out


def clear_all_cache() -> int:
    """删除所有缓存,返回删除的视频条目数"""
    if not CACHE_ROOT.exists():
        return 0
    count = sum(1 for _ in CACHE_ROOT.iterdir() if _.is_dir())
    shutil.rmtree(CACHE_ROOT, ignore_errors=True)
    return count


def clear_cache_for_video(video_id: str) -> bool:
    d = CACHE_ROOT / video_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
        return True
    return False


def cache_summary() -> dict:
    """获取缓存总览:条目数 + 占用字节数"""
    items = list_cached_videos()
    total_size = sum(i["size"] for i in items)
    return {
        "count": len(items),
        "total_bytes": total_size,
        "items": items,
    }
