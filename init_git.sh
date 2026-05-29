#!/usr/bin/env bash
# ============================================================
# 一键初始化 git + 创建 GitHub 仓库 + 推送
# 用法: ./init_git.sh [仓库名] [可见性]
# 例:   ./init_git.sh subtitle-translator public
# ============================================================
set -e
cd "$(dirname "$0")"

REPO_NAME="${1:-subtitle-translator}"
VISIBILITY="${2:-public}"   # public 或 private

VERSION="$(cat VERSION 2>/dev/null || echo 0.1.0)"

log() { printf "\033[1;34m==>\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[!]\033[0m %s\n" "$*"; }
ok() { printf "\033[1;32m✓\033[0m %s\n" "$*"; }

echo
log "字幕生成翻译器 v$VERSION — Git 仓库初始化"
echo

# ---------- 1. git init ----------
if [[ ! -d .git ]]; then
    log "初始化 git 仓库..."
    git init -b main
    ok "git 仓库已建"
else
    ok "git 仓库已存在"
fi

# 配置用户信息(如果还没设过)
if [[ -z "$(git config user.name)" ]]; then
    read -rp "请输入 Git 用户名: " gh_user
    git config user.name "$gh_user"
fi
if [[ -z "$(git config user.email)" ]]; then
    read -rp "请输入 Git 邮箱: " gh_mail
    git config user.email "$gh_mail"
fi

# ---------- 2. 首次提交 ----------
log "添加所有文件并提交..."
git add .
if git diff --cached --quiet; then
    warn "没有可提交的变更"
else
    git commit -m "release: v$VERSION initial commit

- 字幕生成翻译器 v$VERSION
- 双引擎 ASR (Faster-Whisper / OpenAI API)
- 7 家 LLM 翻译模型
- 三级字幕烧录 (libass / drawtext / softmux)
- 阶段性缓存系统
- 浅色/深色主题
- 详见 CHANGELOG.md
"
    ok "已提交"
fi

# ---------- 3. 创建 GitHub 仓库 ----------
if command -v gh >/dev/null 2>&1; then
    log "检测到 gh CLI"

    # 检查是否登录
    if ! gh auth status >/dev/null 2>&1; then
        warn "gh 未登录,运行 gh auth login"
        gh auth login
    fi

    log "通过 gh 创建 GitHub 仓库 ($VISIBILITY): $REPO_NAME"
    if gh repo create "$REPO_NAME" --"$VISIBILITY" \
            --source=. --remote=origin --description "字幕生成翻译器 — 本地视频自动生成多语字幕,支持烧录" \
            --push 2>/dev/null; then
        ok "仓库已创建并推送"
        REPO_URL="$(gh repo view --json url -q .url)"
        ok "仓库主页: $REPO_URL"
    else
        warn "gh repo create 失败,可能仓库已存在"
        warn "尝试只 push..."
        # 假设 origin 已存在或手动设
        if git remote get-url origin >/dev/null 2>&1; then
            git push -u origin main
        else
            warn "未设 origin,请运行:"
            warn "  git remote add origin https://github.com/<用户名>/$REPO_NAME.git"
            warn "  git push -u origin main"
        fi
    fi
else
    warn "未安装 gh CLI"
    echo
    echo "请按以下步骤手动操作:"
    echo
    echo "  1) 浏览器打开 https://github.com/new"
    echo "  2) 仓库名填: $REPO_NAME"
    echo "  3) 不勾任何 README/gitignore/license (已有)"
    echo "  4) 点 Create repository"
    echo
    echo "  5) 复制粘贴这两条命令(把 <用户名> 换成你的):"
    echo
    echo "    git remote add origin https://github.com/<用户名>/$REPO_NAME.git"
    echo "    git push -u origin main"
    echo
    echo "  装 gh CLI 可一键搞定: brew install gh"
fi

echo
ok "完成"
