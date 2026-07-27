# Formal Local Semantic Hint Integration：Preview 边界基线审计

日期：2026-07-27

## 结论

本 Worktree 严格从最新 `main` 创建，但当前 `main` 不包含本轮用户描述的正式 Intelligent Preview 实现。当前 `main` 上不存在：

- `IntelligentExportService`
- `RequestGate`
- `IntentCompiler`
- `DataCatalogBuilder`
- `DateRangeResolver`
- `MovementResolver`
- `ExportPlanValidator`
- `ExportExecutor`
- `intelligent-preview` 或 `/api/intelligent-export/preview` 路由

因此本轮没有可被“修正”的 `run()`→Executor Preview 旁路。相关实现存在于其他实验分支的历史中，但按任务边界不能从 Lab 或实验分支整体复制、合并或 cherry-pick 到本正式集成分支。

继续写代码会从“修正 Preview 边界”扩大为“重新引入整个 Intelligent Export Core”，这不符合本轮只修边界、保持正式 Core 权威、不得整体复制实验实现的要求。因此本 Commit 只记录基线事实和安全阻塞，不修改正式运行代码。

## 当前真实调用链

当前 `main` 的导出入口是传统的 Analysis Export，不是 Intelligent Preview：

```text
Web 前端 buildAnalysisExport()
  → POST /api/analysis-export
  → Web Handler.do_POST()
  → LedgerWebService.analysis_export(request)
  → fitness_ledger_core.analysis_export.build_export()
  → LedgerViewModels.analysis(...)
  → payload + Markdown + JSON
  → 前端复制或浏览器下载
```

对应实现位置：

- `web_desktop/frontend/app.js::buildAnalysisExport`
- `web_desktop/backend/server.py::LedgerWebService.analysis_export`
- `web_desktop/backend/server.py::do_POST` 的 `/api/analysis-export` 分支
- `fitness_ledger_core/analysis_export.py::build_export`

`build_export()` 会调用现有 View Model 读取选定范围，并根据 `include_raw_preview` 请求项构造导出内容；它没有 Executor 类、没有 Plan Validator、没有 `run()`，也没有把返回值自动继续交给其他执行入口。前端收到结果后只提供复制和浏览器下载，不会再次调用后端 Executor。

这条传统导出链路仍然是一个可能包含数据物化和用户下载的 Export 入口，不能被误命名为未来的 Preview-only Intelligent 入口。它也不应在本轮被 SemanticHint 接管。

## `run()` 与 Executor 审查结果

在当前 `main` Worktree 的全部 Python、JavaScript、Markdown 和 JSON 文件中搜索：

- `IntelligentExportService`
- `intelligent-preview`
- `intelligent_export`
- `RequestGate`
- `IntentCompiler`
- `DataCatalogBuilder`
- `DateRangeResolver`
- `MovementResolver`
- `ExportPlanValidator`
- `ExportExecutor`

没有命中当前 `main` 的活动文件。因此：

| 审查项 | 当前 main 事实 |
|---|---|
| Preview 请求何处进入 `run()` | 不存在该请求和入口 |
| Executor 是否执行 | 当前 main 没有该 Executor 实现；传统 `build_export` 不调用名为 Executor 的组件 |
| Web 返回数据来源 | `LedgerViewModels.analysis()` 生成的 payload，经 `build_export()` 包装为 Markdown/JSON |
| 是否存在 Intelligent Preview 旁路 | 未发现；只有传统 `/api/analysis-export` 和动作合并等独立 preview/execute 路由 |
| `IntelligentExportService.run()` 调用位置 | 当前 main 为 0 |
| SemanticHint/Provider/模型调用 | 当前 main 为 0 |

通过 `git log --all -- <path>` 可见上述 Intelligent Export 文件曾在其他实验历史中出现，但它们不属于当前 `main` 树。历史存在不等于正式活动路径，不能据此把实验实现当作本轮正式基线。

## 与目标 Preview-only 边界的差异

用户要求的目标是：

```text
RequestGate
  → IntentCompiler
  → Resolver
  → ExportPlanValidator
  → Preview DTO
```

而当前 `main` 只有传统：

```text
request
  → analysis_export
  → ViewModels.analysis
  → export payload / markdown / json
```

缺少的不是一处路由调用，而是整套正式 Intelligent Export 基础契约。因此现在不能安全地新增一个只返回 Preview DTO 的修补方法，因为它必须同时决定：

- 正式 Request/Plan 的 schema 和版本；
- Gate、Intent、Catalog、Date、Movement 和 Notes 的确定性接口；
- Plan Validator 的权威职责；
- 用户确认与执行入口的交接协议；
- 真实数据 snapshot 和 Raw 权限边界。

这些内容若在当前分支临时补齐，将构成新的 Core 设计，而非边界修正。

## 不应采取的处理方式

- 不从 Lab 分支 cherry-pick 或复制 `RequestDraft`、`DraftAssembler`、SemanticHint、Provider 或测试。
- 不从其他 Intelligent Export 实验分支整体 cherry-pick `fitness_ledger_core` 文件。
- 不把传统 `/api/analysis-export` 重命名为 Intelligent Preview 来掩盖缺失的 Gate/Plan/Validator。
- 不为满足测试而新增一个伪造的 Mock Executor 或假 Preview chain。
- 不让 `build_export()` 继续承担未来确定性 Plan Validator 或用户确认职责。
- 不接入模型、Ollama、qwen3:4b、llama.cpp 或任何 Lab runtime。

## 待正式基线明确后的最小修正方案

只有在提供包含正式 Intelligent Export Core 的明确基线后，才实施以下边界修正：

1. 保持现有 `RequestGate`、`IntentCompiler`、Catalog、Resolvers、`ExportPlanValidator` 和 Executor 不变。
2. 新增或收敛 `AnalysisPreviewService.preview_only()`，只执行 Gate、确定性编译、Resolver、Plan Validator 和匿名 Preview DTO。
3. Web Intelligent Preview 路由只调用 `preview_only()`，静态审计确保不调用 `run()` 和 Executor。
4. 保留现有 Executor，不复制实现；另设独立、明确授权的确认执行入口。
5. 确认执行前重新验证 source snapshot；Preview 响应不可隐式变成执行授权。
6. 增加真实调用计数、文件/数据 hash、Preview DTO/Plan 边界和 Web 路由测试。

最小验收集应包括：Preview 成功/失败时 Executor=0、Preview 不产生文件或写入、显式执行入口仍可调用正式 Executor、Web 路由不达旧 `run()`、Preview DTO 不包含正式 Plan 的可执行副本或 Raw 权限。

## 当前分支与数据状态

| 项目 | 值 |
|---|---|
| Worktree | `C:\Users\26087\Documents\github-memory-worktrees\fl-formal-local-semantic-hint-integration` |
| 分支 | `feat/formal-local-semantic-hint-integration` |
| 基线 HEAD | `0a189162d42cb2b95903d64e9a1d614df00cfe16` |
| `main` | `0a189162d42cb2b95903d64e9a1d614df00cfe16` |
| `origin/main` | `0a189162d42cb2b95903d64e9a1d614df00cfe16` |
| 正式 Tracker | 本轮未读取内容、未修改；启动状态审计仅记录 hash/size/mtime |
| Movement Dictionary | 本轮未读取内容、未修改；启动状态审计仅记录 hash/size/mtime |
| 共享 Ollama | 未调用、未停止、未重启、未修改 |

## 状态决定

本轮**未满足 Preview 边界修正的实施验收**，原因是当前最新 `main` 缺少被要求修正的正式 Intelligent Preview/Core 实现。已完成基线核验并将阻塞事实提交，等待明确一个不违反边界的正式 Core 基线后再继续。

建议下一步由负责人提供以下二选一决策：

- 指定一个已经被正式接受、但尚未合并到 `main` 的 Intelligent Export Core 基线，允许在其上做 Preview-only 边界修正；或
- 明确授权从当前 `main` 新建正式 Core，但这将是独立的架构实施阶段，不再属于本轮边界修正。

## 本轮验证

- `python tools/analysis_export_test.py`：通过（`ANALYSIS_EXPORT_TEST_OK`）。
- Python 编译检查：通过，53 个文件。
- `git diff --check`：在提交前检查通过。
- `tools/web_desktop_test.py`：未能启动，因为当前 `main` Worktree 不包含 Git 管理的 `projects/fitness-ledger/data/tracker.json`；该测试会依赖正式数据文件，因此没有复制外部正式数据来绕过。
- 完整 `tools/regression_test.py`：同样无法作为当前 main 的可信正式回归运行；其入口依赖当前 Worktree 的正式应用/数据状态，缺少上述数据前提。本轮没有伪造结果。
