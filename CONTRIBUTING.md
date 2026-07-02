## 仓库说明

**本仓库以 GitHub 为主仓，GitCode 为镜像。**

- 主仓库地址：https://github.com/MS33834/financial-agent
- GitCode 镜像：https://gitcode.com/badhope/financial-agent

请直接在 **GitHub 主仓** 提交 Issue 和 Pull Request。GitCode 仅用于代码镜像，不处理 Issue/PR。

---

# Contributing

Thank you for your interest in contributing to this project!

## How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Code of Conduct

Please be respectful and constructive in all interactions.

## Questions?

Feel free to open an issue if you have questions or suggestions.

---

## 开发者必做检查清单（每次提交后执行）

> **重要**：每次完成开发任务并推送代码后，**必须**执行以下检查，确保仓库健康状态。
> 任何一项异常都应在下一次提交前修复，不得积压。

### 1. 检查 CI/CD 流水线状态

```bash
# GitHub Actions 最新运行状态（需要 GitHub Token）
gh run list --repo MS33834/financial-agent --limit 5

# 或通过 API 查看
curl -s -H "Authorization: token <TOKEN>" \
  "https://api.github.com/repos/MS33834/financial-agent/actions/runs?per_page=5" \
  | python3 -c "import sys,json; [print(f'{r[\"created_at\"]} | {r[\"head_sha\"][:8]} | {r[\"conclusion\"]}') for r in json.load(sys.stdin)['workflow_runs']]"
```

**要求**：最新一次 push 对应的 CI run 必须为 `success`（全绿）。
- 如果 `failure`：查看失败的 job 和 step，定位原因并修复后重新推送。
- 如果 `in_progress`：等待完成后确认结果。
- 重点关注 `backend`、`frontend`、`compose`、`helm-lint` 四个核心 job。

### 2. 检查 Pull Request

```bash
# 查看开放的 PR
gh pr list --repo MS33834/financial-agent --state open

# 或通过 API
curl -s -H "Authorization: token <TOKEN>" \
  "https://api.github.com/repos/MS33834/financial-agent/pulls?state=open"
```

**要求**：
- 如果有开放 PR：检查是否需要 review、是否有冲突、CI 是否通过。
- 如果有等待合并的 PR：确认 review 通过后合并到 main。
- 合并后确认 main 分支 CI 重新跑通。

### 3. 检查 Issue

```bash
# 查看开放的 Issue
gh issue list --repo MS33834/financial-agent --state open

# 或通过 API
curl -s -H "Authorization: token <TOKEN>" \
  "https://api.github.com/repos/MS33834/financial-agent/issues?state=open"
```

**要求**：
- 如果有开放 Issue：评估是否影响当前版本，分配优先级并排入计划。
- Bug 类 Issue 应优先处理。
- 如果有已解决但未关闭的 Issue：确认后关闭。

### 4. 检查分支状态

```bash
# 查看所有远程分支
git fetch --all --prune
git branch -r

# 或通过 API
curl -s -H "Authorization: token <TOKEN>" \
  "https://api.github.com/repos/MS33834/financial-agent/branches"
```

**要求**：
- 清理已合并的临时分支（删除远程过期分支）。
- 确认 main 分支受保护（branch protection 已启用）。
- 如果有长期未合并的分支：评估是否废弃或合并。

### 5. 检查双仓库同步状态

```bash
# 对比两个远程的 commit hash
git ls-remote github main
git ls-remote gitcode main
```

**要求**：两个远程的 `main` 分支 HEAD commit hash 必须一致。
- 如果不一致：将落后的远程强制同步（`git push <remote> main`）。
- 推送时使用项目根目录的同步脚本：`./scripts/sync_remotes.sh "commit message"`。

### 6. 检查安全告警

```bash
# GitHub Dependabot alerts
gh api repos/MS33834/financial-agent/dependabot/alerts --jq '.[] | select(.state=="open") | .security_advisory.summary'

# 前端依赖扫描
cd frontend && npm audit

# 后端依赖扫描（需安装 pip-audit）
cd backend && pip-audit
```

**要求**：
- `npm audit` 0 vulnerabilities。
- `pip-audit` 无 HIGH/CRITICAL 漏洞。
- GitHub Dependabot 无开放的高危告警。

### 检查结果记录

每次检查后，在提交消息或 PR 描述中简要记录检查结果，例如：

```
## 提交后检查
- CI: ✅ all green (backend/frontend/compose/helm-lint)
- PR: ✅ no open PRs
- Issue: ✅ no open issues
- Branches: ✅ only main, protected
- Sync: ✅ github == gitcode (9a21b7c)
- Security: ✅ npm audit 0 vulns
```

