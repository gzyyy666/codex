# Data Module Human Review Package

这是下一轮人工 Review 的固定入口。候选实现已封装，不再继续增加 Data Module 能力。

## Fixed Candidate

- Worktree：`D:\FitnessLedger\work\fitness-ledger-data-module-candidate-20260812`
- Branch：`codex/fitness-ledger-data-module-candidate-20260812`
- Base：`a63f8a6c3e63e1695898a429ac28a21108957737`
- Implementation Commit：`b77766969d0caf7383c277a5f4ddd8dd0762bc6b` — `Data Module Candidate Implementation`
- Evidence Commit：本包及回归证据提交后记录在最终 handoff 中；该 commit 只包含 Review 文档与 fixture-only 场景脚本。
- 最终 Git Status：提交 evidence 后应为空；不允许保留实现性未提交修改。

## Safety

已复核：

- 正式 tracker SHA-256：`40237d008351a506886e652d541cfc6ca13b65914ae7ae9cb3fc2a78cb2369ae`
- 正式 movement dictionary SHA-256：`6abf5c9a4bb4559a2fa14bd93b3e366a7e339a8fbfab7039746fcd57e269c058`
- 正式 deployment：`CURRENT`，333 个文件无 missing/different。
- Cloud：零 mutation；候选只生成本地 payload、hash、verify 和 roundtrip，`network_request_made=false`。
- Mini：零发布；只读取本地 contract/renderer fixture。
- Remote：零 push、零 merge、零 tag、零 PR。
- `D:\FitnessLedger\app`：零写回。
- `127.0.0.1:8766` 正式 Web 服务未启动；候选预览使用独立 localhost 端口 8767。

## Regression

### Candidate 专项结果

- `python tools/data_module_engine_test.py`：6 tests，PASS。
- `python tools/data_module_static_test.py`：PASS。
- `python tools/data_module_web_candidate_test.py`：PASS。
- `node tools/data_module_mini_contract_test.js`：PASS。
- Python syntax checks：PASS。
- JavaScript syntax checks：PASS。
- `git diff --check`：PASS。
- candidate launcher HTTP smoke：PASS。
- no module-specific business branch、deterministic hash、orphan detection、raw/private leakage gate、Preview zero write、Confirm transactional save、second-module reuse、third-module anti-overfit：全部 PASS。

### Base vs Candidate

共同的 59 个既有 Python 测试在 base 与 candidate 的结果完全一致：base 48 PASS / 11 FAIL，candidate 48 PASS / 11 FAIL，`CANDIDATE_REGRESSION = 0`。

| Test | Base result | Candidate result | Base failure reason | Candidate failure reason | Classification |
|---|---:|---:|---|---|---|
| `analysis_export_protocol_web_test.py` | FAIL | FAIL | 旧前端精确文本断言 `"???" not in app` 失败 | 相同 | TEST_ASSERTION_DRIFT |
| `formal_readonly_export_binding_test.py` | FAIL | FAIL | 匿名数据记录数不满足固定 13 条断言 | 相同 | FIXTURE_LIMITATION |
| `intelligent_export_core_test.py` | FAIL | FAIL | 匿名 fixture 没有可供断言的 movement 行，`IndexError` | 相同 | FIXTURE_LIMITATION |
| `intelligent_export_review_evidence_test.py` | FAIL | FAIL | 既有 review fixture 缺 candidate/intent/selection/snapshot/target scope | 相同 | FIXTURE_LIMITATION |
| `intelligent_export_selection_test.py` | FAIL | FAIL | 既有匿名输入未生成 `selection` | 相同 | FIXTURE_LIMITATION |
| `movement_identity_ux_test.py` | FAIL | FAIL | 旧 Web 文本精确断言找不到“只有确为同一动作时才合并” | 相同 | TEST_ASSERTION_DRIFT |
| `movement_progress_cache_test.py` | FAIL | FAIL | 旧 JS 精确字符串断言漂移 | 相同 | TEST_ASSERTION_DRIFT |
| `notes_semantics_core_test.py` | FAIL | FAIL | `FormalReadOnlyDataSourceError: Formal structured data contains no usable dates` | 相同 | FIXTURE_LIMITATION |
| `regression_test.py` | FAIL | FAIL | 匿名 movement dictionary 少于固定 29 条 | 相同 | FIXTURE_LIMITATION |
| `smoke_test.py` | FAIL | FAIL | 匿名 dictionary 缺少旧 smoke 期待的动作 | 相同 | FIXTURE_LIMITATION |
| `web_desktop_test.py` | FAIL | FAIL | 匿名仓库没有 `data/movement_dictionary.json` | 相同 | FIXTURE_LIMITATION |

`shadow_planner_ollama_shadow_test.py` 未纳入共同对照，原因是它依赖外部 Ollama，分类为 `EXTERNAL_DEPENDENCY`；未因此改变任何业务或测试断言。

## Preview

从 Candidate Worktree 根目录执行一个入口：

```powershell
python projects\fitness-ledger\tools\run_data_module_candidate_preview.py --open
```

也可以双击：

`D:\FitnessLedger\work\fitness-ledger-data-module-candidate-20260812\projects\fitness-ledger\tools\run_data_module_candidate_preview.cmd`

打开 URL：

`http://127.0.0.1:8767/data-module-candidate.html`

关闭方式：回到启动窗口按 `Ctrl+C`；临时匿名 tracker、dictionary、backups 会随进程退出自动删除。若 8767 被占用，可只把端口改为 8768，URL 同步改端口；不需要设置环境变量，不需要复制 fixture。

使用的 fixture：`projects/fitness-ledger/tools/fixtures/data_modules/registry.json`，包括 `waist_cm` 与 `resting_hr`；数据文件是启动器运行时在系统临时目录创建的匿名文件，不是正式 tracker。

## Human Review Scenarios

### A — 创建/识别第一个 Numeric Module

1. 打开 Preview，默认文本为 `2026-08-12 腰围 82.5 cm；静息心率 62 bpm`。
2. 点击“预览（零写入）”。
3. 检查返回的 `status=preview_ready`、`write_attempted=false`，以及候选中的 `waist_cm`。
4. 在不保存的情况下刷新页面，确认没有正式或候选 fixture 记录被写入。

### B — Confirm / History

1. 对 A 的 preview 点击“确认保存匿名夹具”。
2. 检查保存结果为 `CREATED`，并观察 Mini 卡片的历史数量变化。
3. 直接打开：`http://127.0.0.1:8767/api/data-modules/history?module_id=waist_cm`。
4. 判断记录是否具有稳定 `record_id`、日期、value、actual unit、definition version，而不是临时 UI 状态。

### C — 第二模块泛化

1. 将输入改为 `2026-08-13 静息心率 62 bpm`。
2. 重复 Preview → Confirm。
3. 检查 `resting_hr` 使用相同流程生成记录；下方 downstream 区域的 Normal Export record count 应增加，Mini renderer 同时出现 `single_metric` 与 `metric_history`。
4. 判断是否能看出新增模块没有专属页面/保存分支。

### D — Schema Evolution

在 Preview 终端的 Candidate Worktree 根目录执行：

```powershell
python projects\fitness-ledger\tools\data_module_review_scenarios.py
```

这是 fixture-only、一次性、无正式写入的脚本。重点检查输出中的 `D_schema_evolution`：

- `stable_module_id=true`；
- `version_after` 高于 `version_before`；
- `history_visible_after_retire=true`；
- `new_record_blocked_code=MODULE_NOT_RECORDABLE`；
- `formal_registry_written=false`。

### E — Downstream Capability

在页面下方点击“刷新 Export / Analysis / Cloud dry-run / Mini”。重点判断：

- Normal Export 是否自动包含已注册模块与记录；
- Analysis gate 是否只展示 `analysis_visible=true` 的 `waist_cm`，并隐藏 `resting_hr`；
- Cloud dry-run 是否显示 payload hash、`network_request_made=false`、`raw_policy=excluded`；
- Mini renderer contract 是否显示两个有限 renderer；
- 是否没有发生 Cloud 上传、Mini 发布或 AnalysisExportRequest v1.1 变化。

## What I am reviewing

本轮主要请判断：

1. 新增数据模块的行为是否符合预期；
2. Registry-driven 泛化是否自然，而不是把旧 Core 复制一套；
3. Parse → Preview → Save → History 是否顺畅、可追踪、可回滚；
4. Normal Export、Analysis gate、Cloud dry-run、Mini renderer contract 是否随模块能力自然跟随；
5. 当前 Candidate 是否值得进入正式 UI / New Category / Placement 阶段。

## Explicitly not yet production

本 Candidate 仍未进行：

- main merge；
- push；
- production deployment；
- formal tracker migration；
- CloudBase upload；
- Mini Program publish；
- AnalysisExportRequest public protocol change；
- New Category；
- formal Placement。

人工 Review 完成前，不应把 registry 或 `data_module_records` 写入 `D:\FitnessLedger\app`，也不应启动正式 8766 Web 服务或线上同步流程。
