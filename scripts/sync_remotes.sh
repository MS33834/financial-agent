#!/usr/bin/env bash
# 双远程同步脚本：把当前分支推送到 GitHub 和 GitCode
# 用法: ./scripts/sync_remotes.sh [commit_message]
set -euo pipefail

MSG="${1:-chore: sync across remotes}"

# 检查是否有变更需要提交
if ! git diff --quiet || ! git diff --cached --quiet; then
  git add -A
  git commit -m "$MSG"
fi

BRANCH=$(git rev-parse --abbrev-ref HEAD)

echo "==> Pushing to GitHub ($BRANCH)"
git push github "$BRANCH"

echo "==> Pushing to GitCode ($BRANCH)"
git push gitcode "$BRANCH"

echo "==> Sync complete."
