"""单一版本号来源 — VERSION 文件读取,所有地方引用这里"""
from pathlib import Path

_root = Path(__file__).resolve().parent
try:
    __version__ = (_root / "VERSION").read_text(encoding="utf-8").strip()
except OSError:
    __version__ = "0.1.0"

VERSION = __version__
APP_NAME = "字幕生成翻译器"
APP_NAME_EN = "Subtitle Translator"
BUNDLE_ID = "com.subtitletools.translator"
