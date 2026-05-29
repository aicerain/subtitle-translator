#!/usr/bin/env bash
# 把 assets/icon.iconset 转换成 assets/icon.icns
# 仅在 macOS 上可用(依赖系统自带的 iconutil)
set -euo pipefail

cd "$(dirname "$0")"
ROOT="$(pwd)"

if ! command -v iconutil >/dev/null 2>&1; then
    echo "错误: 未找到 iconutil。这个命令是 macOS 自带的,请确认在 Mac 上运行。"
    exit 1
fi

[[ -d icon.iconset ]] || {
    echo "错误: assets/icon.iconset 不存在,请先运行 python generate_icon.py"
    exit 1
}

# 校验 iconset 内容
required=(
    "icon_16x16.png" "icon_16x16@2x.png" "icon_32x32.png" "icon_32x32@2x.png"
    "icon_128x128.png" "icon_128x128@2x.png" "icon_256x256.png" "icon_256x256@2x.png"
    "icon_512x512.png" "icon_512x512@2x.png"
)
for f in "${required[@]}"; do
    [[ -f "icon.iconset/$f" ]] || {
        echo "错误: 缺少 icon.iconset/$f,请重新运行 generate_icon.py"
        exit 1
    }
done

echo "==> iconutil 打包 .icns ..."
iconutil -c icns icon.iconset -o icon.icns
echo "✅ 已生成: $ROOT/icon.icns"
ls -la icon.icns
