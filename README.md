# GitHub Memory System

这是一个把个人工作流、偏好、项目背景和决策记录工程化管理的最小模板。建议把整个目录作为一个 GitHub 仓库维护，让 Codex 在需要时读取、更新、归档这些 Markdown 节点。

## 目录结构

- `memory/`: 长期记忆节点，例如个人偏好、项目背景、协作上下文。
- `decisions/`: 技术或工作流决策记录，使用 ADR 风格。
- `workflows/`: 可复用流程，例如周复盘、想法拆解为 GitHub Issues。
- `skills/`: 可安装到 Codex 的自定义 Skill。
- `templates/`: 新建记忆节点、决策、Issue 时复用的模板。

## 推荐使用方式

1. 在 GitHub 创建一个私有仓库，例如 `personal-memory-system`。
2. 把本目录内容推送到仓库。
3. 日常让 Codex 读取这个仓库里的 `memory/` 和 `workflows/`，再执行具体任务。
4. 当出现新的稳定偏好、长期项目背景或重要决策时，让 Codex 新增或更新记忆节点。
5. 每周运行一次 `workflows/weekly-review.md`，把临时记录整理成可追踪资产。

## 记忆边界

适合写入：

- 长期偏好
- 反复出现的项目背景
- 可复用工作流
- 重要决策及原因
- 不含敏感信息的协作上下文

不适合写入：

- 密码、令牌、Cookie、私钥
- 身份证、银行卡、家庭住址等敏感个人信息
- 未经允许的他人隐私
- 一次性临时信息

## Codex Skill

`skills/github-memory/` 是一个最小可用 Skill。安装到 Codex 后，可以用类似请求触发：

```text
Use $github-memory to update my project preference memory based on this discussion.
```

或者中文：

```text
使用 $github-memory，把这次讨论沉淀成一个新的记忆节点。
```

## New Conversation Startup

For other Codex conversations, start from `START_HERE.md`. It contains a default startup prompt and a recovery prompt for rebuilding context from this repository.
