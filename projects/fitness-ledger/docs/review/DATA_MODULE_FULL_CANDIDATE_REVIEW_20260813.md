# Fitness Ledger Data Module Full Candidate Review

> Closure note: this is the pre-closure architecture/implementation report. The fixed object for the next human review is [Data Module Human Review Package](DATA_MODULE_HUMAN_REVIEW_PACKAGE_20260813.md).

日期：2026-08-13（候选实施快照）

范围：仅隔离 candidate worktree、匿名夹具、离线 dry-run；未写入正式业务数据、CloudBase、线上小程序或远端仓库。

## 1. Git 与正式基线

- Worktree：`D:\FitnessLedger\work\fitness-ledger-data-module-candidate-20260812`
- Branch：`codex/fitness-ledger-data-module-candidate-20260812`
- Base / HEAD：`a63f8a6c3e63e1695898a429ac28a21108957737`
- local `main`：同上；`origin/main`：`d1759117553a8d28437a16c6d456cf6121ba744c`；local main ahead 4、behind 0。
- candidate 当前为未提交工作树，未 push、merge、tag、PR。
- 原工作树的既有未提交文件仍保持原样：`projects/fitness-ledger/AGENTS.md`、`docs/INDEX.md`、`docs/agent/`。

正式业务快照在前后核对一致：

- `D:\FitnessLedger\app\data\tracker.json` SHA-256：`40237d008351a506886e652d541cfc6ca13b65914ae7ae9cb3fc2a78cb2369ae`
- `D:\FitnessLedger\app\data\movement_dictionary.json` SHA-256：`6abf5c9a4bb4559a2fa14bd93b3e366a7e339a8fbfab7039746fcd57e269c058`
- Desktop deployment：`CURRENT`，333 个文件无 missing/different。
- Cloud 状态：仍为既有 `SYNCED` 快照，未同步本次候选内容。
- 本地 Web 服务 `127.0.0.1:8766` 未启动。

## 2. Candidate 架构

新增 `fitness_ledger_core/data_module_engine.py`，Data Module 是 Core Body/Diet/Training/Movement 之外的 Extension Layer，不替换原有模型。

链路为：

`Definition → Registry → alias recognition → Preview → deterministic validation → Confirm → existing LedgerCommandService lock/checkpoint/_write_pair → data_module_records → query/history/export/Data Check → capability-gated Analysis catalog → Cloud dry-run → Mini renderer contract`

关键约束：

- `module_id` 是稳定 ID；label、alias、category、data type、actual/display unit、definition version、status、capabilities、validation、recording behavior、presentation 均进入定义。
- Registry 负责定义校验、ID/alias 冲突、排序、版本历史、alias lookup、capability catalog。
- 记录使用列表形态 `data_module_records`，为未来 multiple-per-day/event/session/meal/structured 保留接口；本候选实际只落地 scalar + one-per-day，其他行为明确拒绝并报告 deferred。
- Parser 只读 Registry alias，不包含 `waist_cm`、`resting_hr` 或其他模块 ID 分支。
- Preview 明确 `write_attempted=false`，Confirm 后才进入现有成对写入边界；原始输入保留在 `raw_entries`。
- `NO_CHANGES`、锁、检查点、原子写、失败回滚、Undo 复用既有命令层。

## 3. 覆盖状态

### IMPLEMENTED

- 通用 Module Definition / Registry / validation / collision / alias / version / order / capability catalog。
- 两个 numeric module fixture：`waist_cm`、`resting_hr`。
- 第三个 `body_fat_pct` anti-overfit fixture；同一 Parser/Save/Query/Export/Data Check/Cloud/Mini 链路，无模块 ID 专用分支。
- Raw → Parse → Preview → Validate → Confirm → Save → Query/History。
- 普通 Data Module export、Data Check（definition/record/capability/version/orphan）。
- Analysis provider/catalog/visibility gate；`analysis_visible=false` 不进入 analysis preview；不改 AnalysisExportRequest v1.1。
- Cloud extension payload、能力过滤、确定性 payload/collection hash、verify、roundtrip、raw/private/orphan 检查；`network_request_made=false`。
- Mini 本地 contract 与有限 renderer：`single_metric`、`metric_history`；empty/retired/unsupported renderer 均有校验。
- Presentation section/slot/order/visible-by-default/fallback/unsupported behavior 校验。
- Fixture-only migration plan/apply/rollback/stale/idempotency；实际 unit 改动没有显式 factor/offset 会被阻断。
- Desktop/Web adapter：只有显式配置 `FITNESS_LEDGER_DATA_MODULE_REGISTRY` 时才启用候选 API；默认业务路径不受影响。
- 本地候选预览页：`/data-module-candidate.html`，仅用于本地 review，不是最终 UI。

### DRY-RUN ONLY

- Cloud 上传、CloudBase collection 写入、线上小程序读取、正式 migration tracker、正式 registry 持久化。
- 候选 HTTP 服务只在临时匿名文件上运行。

### CONTRACT ONLY

- event/session/meal/structured 的正式保存实现。
- Analysis 公共协议字段变更；当前停在 `AnalysisExportRequest-v1.1-boundary`。
- 最终桌面 UI、正式小程序页面布局、Cloud 生产映射。

### DEFERRED

- 正式 module 定义落点、正式 module ID/label/alias/capability 决策。
- 真实历史数据迁移及实际 unit 迁移。
- CloudBase 与线上 Mini Program 的正式改动和发布。
- 任何旧 paused Custom Daily Metric 分支的整体恢复。

## 4. Schema evolution 与安全证据

匿名 fixture 已验证：

- label/alias/category/display unit 变更会提升 definition version，并保存历史 snapshot；`module_id` 不可变。
- actual unit 变更没有显式 migration 会被拒绝；有 factor/offset 才能生成 fixture migration plan。
- retire/re-enable、stale plan、重复 apply、rollback、坏值、orphan record、future version 均可检测或阻断。
- Data Module Cloud payload 不包含 raw text、private、notes、source raw hash；hash 不一致或 orphan 会被拒绝。
- Analysis hidden module 会被拒绝，不能只因存在记录就进入 analysis。
- Mini 只允许有限 renderer；未知 renderer 不会静默 fallback 成错误展示。

## 5. 测试

候选专用测试：

- `python tools/data_module_engine_test.py`：6 tests，PASS。
- `python tools/data_module_static_test.py`：PASS；检查 engine 无具体 module ID 分支、确定性 hash、orphan/cloud/raw 泄漏门禁。
- `python tools/data_module_web_candidate_test.py`：PASS；真实本地 HTTP preview/save/query/cloud verify/roundtrip/Mini contract。
- `node tools/data_module_mini_contract_test.js`：PASS。
- Python/JavaScript syntax checks：PASS。
- `git diff --check`：PASS。

仓库现有 `tools/*test.py` 全量扫描（当时 62 项）：50 PASS，12 项未通过。失败均已记录为既有匿名仓库/外部依赖限制或旧断言漂移，未见 Data Module 候选专用失败：

- 缺正式 fixture/结构化数据：`formal_readonly_export_binding_test.py`、`notes_semantics_core_test.py`、`regression_test.py`、`smoke_test.py`、`web_desktop_test.py`，以及依赖正式数据的部分 intelligent export 测试。
- 旧文本/前端精确断言漂移：`analysis_export_protocol_web_test.py`、`movement_identity_ux_test.py`、`movement_progress_cache_test.py`。
- 外部 Ollama 依赖：`shadow_planner_ollama_shadow_test.py` 未返回；已仅终止命令行完全匹配的两个测试进程，未改项目文件。
- 与本候选直接相关的既有回归（save、cloud、mini、ledger web read、project status、PWA 等）通过。

## 6. 电源与人审门

只读检查到当前电源方案为“平衡”：交流睡眠 900 秒、休眠 1800 秒；本轮未修改电源设置，也未让正式电脑进入长时间任务状态。候选测试已完成，未产生需要保持唤醒的后台任务。

下一步必须由人确认：

1. 审阅本报告与 candidate diff，确认 Registry 定义和 `data_module_records` 形态。
2. 明确第一批正式模块、别名、单位、category、analysis/cloud/mini capability。
3. 明确是否允许接入正式桌面、小程序与 CloudBase；在此之前不做任何线上或正式数据写回。
4. 如 Analysis 需要公开协议字段变化，单独进行 v1.1 协议评审。
5. 真实数据 migration 需另行批准并使用已审计 plan/backup/rollback。

结论：候选实现已具备下一轮 review 所需的可运行证据，但尚未达到“可直接写入正式业务”的授权状态。
