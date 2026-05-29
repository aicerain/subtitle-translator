#!/usr/bin/env bash
# macOS 显示异常诊断脚本
# 如果上次运行本应用后系统进入"屏幕异常休眠",运行此脚本可定位/恢复
set -u

log() { printf "\033[1;34m==>\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[警告]\033[0m %s\n" "$*"; }
ok() { printf "\033[1;32m[正常]\033[0m %s\n" "$*"; }

log "1) 检查残留的电源断言 (Power Assertions)..."
echo "----------------------------------------"
pmset -g assertions | head -60
echo "----------------------------------------"
echo
echo "[说明] 如看到 PreventDisplaySleep / NoDisplaySleepAssertion 的 PID 数量异常,"
echo "       或仍存在 python / SubtitleTranslator 进程持有的断言,请重启该进程或电脑。"
echo

log "2) 查找仍在运行的本程序进程..."
PROCS=$(pgrep -fl "SubtitleTranslator|main\.py" || true)
if [[ -z "$PROCS" ]]; then
    ok "未发现本程序遗留进程"
else
    warn "发现遗留进程:"
    echo "$PROCS"
    read -rp "  → 是否强制结束这些进程?[y/N] " ans
    if [[ "${ans:-N}" =~ ^[Yy] ]]; then
        pkill -9 -f "SubtitleTranslator" 2>/dev/null || true
        pkill -9 -f "python.*main\.py" 2>/dev/null || true
        ok "已强制结束"
    fi
fi
echo

log "3) 检查显示器休眠/亮屏时间设置..."
pmset -g | grep -E "displaysleep|sleep" | head -5
echo

log "4) 一键恢复显示子系统(可选,需要管理员密码)"
echo "  方案 A:重置 windowserver(瞬间黑屏几秒后恢复)"
echo "    sudo killall WindowServer"
echo
echo "  方案 B:重置显示器休眠时间到默认 10 分钟"
echo "    sudo pmset -a displaysleep 10"
echo
echo "  方案 C(最彻底):重启 Mac"
echo
log "诊断完成。"
