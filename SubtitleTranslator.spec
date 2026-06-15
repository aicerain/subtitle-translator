# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec - 跨平台,但 .app 仅在 macOS 上生成
# 使用: pyinstaller SubtitleTranslator.spec --clean --noconfirm

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# 项目根
ROOT = Path(SPECPATH)

# 从 VERSION 文件读取版本
try:
    APP_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
except OSError:
    APP_VERSION = "0.1.0"

# PyQt6 多媒体依赖在 PyInstaller 默认 hook 里有时漏掉
hiddenimports = [
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.sip",
    # 注:不再使用 QtMultimedia / QtMultimediaWidgets,
    # 因为它们在 macOS 上会注册 IOPMAssertion 导致黑屏。
    # 预览改用 ffmpeg 提关键帧 + QLabel 显示。
    # OpenAI / Anthropic SDK
    "openai",
    "anthropic",
    # Whisper
    "faster_whisper",
    "ctranslate2",
    "tokenizers",
    "onnxruntime",
    # 字幕
    "pysrt",
] + collect_submodules("yt_dlp")

datas = []
# 如有图标资源、配置默认值文件等,可以放进去
# datas += [("assets/icon.icns", "assets")]

a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除大而无用的依赖,减小体积
        "tkinter", "test", "tests",
        "matplotlib", "scipy", "pandas", "PIL",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SubtitleTranslator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                       # macOS 上 UPX 会破坏代码签名,关闭
    console=False,                    # GUI 应用,不开终端
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,                 # 用当前 Python 架构 (Apple Silicon -> arm64)
    codesign_identity=None,           # 如有开发者证书可填 "Developer ID Application: Your Name"
    entitlements_file=None,
    icon=str(ROOT / "assets" / "icon.icns") if (ROOT / "assets" / "icon.icns").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SubtitleTranslator",
)

# 只在 macOS 上构造 .app
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="SubtitleTranslator.app",
        icon=str(ROOT / "assets" / "icon.icns") if (ROOT / "assets" / "icon.icns").exists() else None,
        bundle_identifier="com.subtitletools.translator",
        version=APP_VERSION,
        info_plist={
            "CFBundleName": "SubtitleTranslator",
            "CFBundleDisplayName": "字幕生成翻译器",
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": APP_VERSION,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            # 允许应用读取用户选择的视频/字幕文件
            "NSDocumentsFolderUsageDescription": "需要读取你选择的视频文件以生成字幕。",
            "NSDesktopFolderUsageDescription": "需要读取桌面上的视频文件以生成字幕。",
            "NSDownloadsFolderUsageDescription": "需要读取下载目录中的视频文件以生成字幕。",
            "NSRemovableVolumesUsageDescription": "需要读取外部存储中的视频文件以生成字幕。",
            # 支持的文件类型(双击视频文件可用本应用打开)
            "CFBundleDocumentTypes": [
                {
                    "CFBundleTypeName": "Video File",
                    "CFBundleTypeRole": "Viewer",
                    "LSItemContentTypes": [
                        "public.mpeg-4", "public.movie", "public.video",
                        "com.apple.quicktime-movie",
                    ],
                }
            ],
        },
    )
