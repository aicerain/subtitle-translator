#!/usr/bin/env bash
# 给最终用户的「源码运行」一键安装脚本(不打包,直接运行 main.py)
# 同样基于 miniforge / conda
set -euo pipefail

cd "$(dirname "$0")"

ENV_NAME="subtitle-translator"
PY_VER="3.11"

log() { printf "\033[1;34m==>\033[0m %s\n" "$*"; }
fail() { printf "\033[1;31m[错误]\033[0m %s\n" "$*"; exit 1; }

# 1. miniforge / conda
CONDA_BIN=""
for c in "$HOME/miniforge3/bin/conda" "$HOME/mambaforge/bin/conda" \
         "/opt/homebrew/Caskroom/miniforge/base/bin/conda" \
         "/opt/miniforge3/bin/conda" "/opt/homebrew/bin/conda" \
         "/opt/homebrew/anaconda3/bin/conda" "$HOME/anaconda3/bin/conda" \
         "$HOME/miniconda3/bin/conda"; do
    [[ -x "$c" ]] && CONDA_BIN="$c" && break
done
[[ -z "$CONDA_BIN" ]] && command -v conda >/dev/null 2>&1 && CONDA_BIN="$(command -v conda)"
[[ -z "$CONDA_BIN" ]] && fail "未找到 conda / miniforge,请先 'brew install --cask miniforge'"

log "使用 conda: $CONDA_BIN"
# 直接用 conda 自身的 hook 初始化,不依赖任何特定的安装根路径
# 这样对 brew symlink (/opt/homebrew/bin/conda) 也能正确工作
# shellcheck disable=SC1091
eval "$("$CONDA_BIN" shell.bash hook)"

# 2. 环境
if ! conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
    log "创建 conda 环境 $ENV_NAME ..."
    conda create -y -n "$ENV_NAME" python="$PY_VER"
fi
conda activate "$ENV_NAME"
log "Python: $(which python)"

# 3. 依赖
log "安装依赖..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 4. FFmpeg
if ! command -v ffmpeg >/dev/null 2>&1; then
    log "未发现 ffmpeg,尝试 brew 安装..."
    if command -v brew >/dev/null 2>&1; then
        brew install ffmpeg
    else
        echo "请手动安装 ffmpeg:  https://ffmpeg.org/download.html"
    fi
fi

log "✅ 完成!以后启动方式:"
echo "    conda activate $ENV_NAME && python main.py"
echo
log "立即启动?"
read -rp "  [y/N] " ans
if [[ "${ans:-N}" =~ ^[Yy] ]]; then
    python main.py
fi
