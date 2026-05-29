#!/usr/bin/env bash
# 把 dist/SubtitleTranslator.app 打包成可拖拽安装的 .dmg
# 优先使用 create-dmg(美观),没有就用系统 hdiutil 兜底
set -euo pipefail

cd "$(dirname "$0")"
APP="dist/SubtitleTranslator.app"
DMG="dist/SubtitleTranslator.dmg"
VOL_NAME="SubtitleTranslator"

[[ -d "$APP" ]] || { echo "错误: 未找到 $APP,请先运行 build_mac.sh"; exit 1; }
rm -f "$DMG"

log() { printf "\033[1;34m==>\033[0m %s\n" "$*"; }

# 优先 create-dmg(brew install create-dmg)
if command -v create-dmg >/dev/null 2>&1; then
    log "使用 create-dmg 生成美观 DMG..."
    create-dmg \
        --volname "$VOL_NAME" \
        --window-pos 200 120 \
        --window-size 600 360 \
        --icon-size 100 \
        --icon "SubtitleTranslator.app" 150 180 \
        --hide-extension "SubtitleTranslator.app" \
        --app-drop-link 450 180 \
        --no-internet-enable \
        "$DMG" \
        "$APP"
    log "✅ DMG 已生成: $DMG"
    exit 0
fi

# 兜底:用 hdiutil
log "未检测到 create-dmg,使用 hdiutil 简单打包..."
log "(建议: brew install create-dmg 获得更好效果)"

STAGE=$(mktemp -d)
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create \
    -volname "$VOL_NAME" \
    -srcfolder "$STAGE" \
    -ov -format UDZO \
    "$DMG"
rm -rf "$STAGE"

log "✅ DMG 已生成: $DMG"
log "体积: $(du -sh "$DMG" | cut -f1)"
