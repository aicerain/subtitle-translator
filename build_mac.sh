#!/usr/bin/env bash
# ============================================================================
# Mac 本地一键打包脚本(基于 miniforge / conda)
# 流程:
#   1. 定位 miniforge,初始化 conda
#   2. 创建/复用 conda 环境 "subtitle-translator" (Python 3.11)
#   3. 安装 PyQt6 / faster-whisper / openai / anthropic / pyinstaller 等
#   4. 用 PyInstaller + spec 生成 dist/SubtitleTranslator.app
#   5. 调用 create_dmg.sh 打成 .dmg
# ============================================================================

set -euo pipefail

cd "$(dirname "$0")"
ROOT="$(pwd)"

# ---------- 工具函数 ----------
log()   { printf "\033[1;34m==>\033[0m %s\n" "$*"; }
warn()  { printf "\033[1;33m[警告]\033[0m %s\n" "$*"; }
fail()  { printf "\033[1;31m[错误]\033[0m %s\n" "$*"; exit 1; }

ENV_NAME="subtitle-translator"
PY_VER="3.11"

# ---------- 1. 定位 conda ----------
log "查找 miniforge / conda..."

CONDA_BIN=""
CANDIDATES=(
    "$HOME/miniforge3/bin/conda"
    "$HOME/mambaforge/bin/conda"
    "/opt/homebrew/Caskroom/miniforge/base/bin/conda"
    "/opt/miniforge3/bin/conda"
    "/opt/homebrew/bin/conda"
    "/opt/homebrew/anaconda3/bin/conda"
    "$HOME/anaconda3/bin/conda"
    "$HOME/miniconda3/bin/conda"
    "/usr/local/bin/conda"
)
for c in "${CANDIDATES[@]}"; do
    if [[ -x "$c" ]]; then
        CONDA_BIN="$c"
        break
    fi
done

# 退而求其次:从 PATH 找
if [[ -z "$CONDA_BIN" ]] && command -v conda >/dev/null 2>&1; then
    CONDA_BIN="$(command -v conda)"
fi

[[ -z "$CONDA_BIN" ]] && fail "未找到 miniforge / conda。请先安装:\n  brew install --cask miniforge\n  或 https://github.com/conda-forge/miniforge"

log "使用 conda: $CONDA_BIN"

# 用 conda 自身的 shell hook 初始化 — 兼容任何安装方式,
# 包括 brew symlink (/opt/homebrew/bin/conda) 和自定义路径
# shellcheck disable=SC1091
eval "$("$CONDA_BIN" shell.bash hook)"

# ---------- 2. 创建/复用环境 ----------
if conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
    log "环境 '$ENV_NAME' 已存在,直接复用"
else
    log "创建 conda 环境 '$ENV_NAME' (Python $PY_VER)..."
    conda create -y -n "$ENV_NAME" python="$PY_VER"
fi

conda activate "$ENV_NAME"
log "已激活: $(python --version)  在 $(which python)"

# ---------- 3. 安装依赖 ----------
log "升级 pip..."
python -m pip install --upgrade pip wheel setuptools

log "安装项目依赖..."
python -m pip install -r requirements.txt

log "安装 PyInstaller..."
python -m pip install --upgrade "pyinstaller>=6.0"

# 检查 ffmpeg 是否在系统中
if ! command -v ffmpeg >/dev/null 2>&1; then
    warn "系统中未检测到 ffmpeg。"
    warn "应用运行需要 FFmpeg,建议先 'brew install ffmpeg'。"
    warn "(打包不依赖 ffmpeg,但用户运行 .app 时需要它)"
fi

# ---------- 4. 清理 + PyInstaller ----------
log "清理旧构建..."
rm -rf build dist

VERSION="$(cat VERSION 2>/dev/null || echo 0.1.0)"
log "PyInstaller 开始打包 v$VERSION..."
pyinstaller SubtitleTranslator.spec --clean --noconfirm

APP_PATH="dist/SubtitleTranslator.app"
[[ -d "$APP_PATH" ]] || fail "未生成 $APP_PATH,请查看上方日志"

log "App 已生成: $APP_PATH"
log "App 体积: $(du -sh "$APP_PATH" | cut -f1)"

# 生成图标(如果还没生成)
if [[ ! -f assets/icon.icns ]] && [[ -x assets/make_icns.sh ]]; then
    log "生成 macOS 图标..."
    pushd assets >/dev/null && ./make_icns.sh && popd >/dev/null
fi

# ---------- 5. 打 DMG ----------
if [[ -x "$ROOT/create_dmg.sh" ]]; then
    log "调用 create_dmg.sh 打包 .dmg..."
    "$ROOT/create_dmg.sh"
    # 加版本号
    if [[ -f dist/SubtitleTranslator.dmg ]]; then
        mv dist/SubtitleTranslator.dmg "dist/SubtitleTranslator-${VERSION}-macOS.dmg"
        log "✅ DMG 已重命名: dist/SubtitleTranslator-${VERSION}-macOS.dmg"
    fi
else
    warn "create_dmg.sh 不存在或不可执行,跳过 DMG 步骤。"
fi

echo
echo "============================================================"
echo "  ✅  v${VERSION} 打包完成!"
echo
echo "  产物:"
echo "    dist/SubtitleTranslator.app                       (拖到 /Applications)"
[[ -f "dist/SubtitleTranslator-${VERSION}-macOS.dmg" ]] && echo "    dist/SubtitleTranslator-${VERSION}-macOS.dmg    (分发给其他 Mac 用户)"
echo
echo "  首次运行须知:"
echo "    1) 需预装 ffmpeg(推荐 ffmpeg-full 享受 libass 硬字幕):"
echo "       brew install ffmpeg-full"
echo
echo "    2) 若提示\"无法打开,来自未知开发者\":"
echo "       xattr -dr com.apple.quarantine /Applications/SubtitleTranslator.app"
echo "============================================================"
