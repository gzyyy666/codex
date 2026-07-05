# Codex Memory And Project Archive

这是一个版本化的长期上下文仓库，用于保存可复用的项目状态、决策、工作流和非敏感源码快照。它不是原始聊天备份，也不保存密码、令牌或个人数据库。

## 从哪里开始

- 新对话或上下文恢复：`START_HERE.md`
- Fitness Ledger：`projects/fitness-ledger/START_HERE.md`
- 长期项目索引：`memory/projects.md`
- 重要决策：`decisions/`
- 可复用流程：`workflows/`

## 目录

- `memory/`: 当前事实、偏好和项目状态
- `decisions/`: 影响后续行为的 ADR 决策
- `workflows/`: 可重复执行的维护与恢复流程
- `projects/`: 不含个人数据的项目源码与文档快照
- `skills/`: Codex 自定义 Skill
- `templates/`: 新节点、决策和 Issue 模板

## 基本规则

1. 优先更新已有节点，避免同一事实多处重复。
2. 保存结论、边界和恢复方法，不保存原始聊天全文。
3. 项目源码与个人数据分开：Git 负责源码回退，本地自动备份负责数据回退。
4. 只有经过测试的稳定节点才提交和标记。
5. 不提交 `data/`、备份、浏览器配置、缓存、临时 QA 截图或凭据。

## Fitness Ledger 快速恢复

```text
Read START_HERE.md, then projects/fitness-ledger/START_HERE.md.
Use projects/fitness-ledger/docs/INDEX.md to select only the context needed for the current task.
Do not inspect or overwrite live personal data.
```
