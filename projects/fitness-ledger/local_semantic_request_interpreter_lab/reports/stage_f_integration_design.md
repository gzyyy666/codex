# Stage F：Local Semantic Interpreter 受控产品集成设计报告

日期：2026-07-27
范围：只读审查与实施设计；本轮不复制 Lab 代码、不修改正式 Core、不调用 Executor、不访问正式数据内容。

## 结论

当前 Lab 候选可以进入“受控集成设计完成、等待新分支实施”的状态，但不能直接进入正式产品，也不应把 Lab 分支整体合并到 `main`。

建议先封存本 Lab 候选证据，再从独立集成分支实施一个很薄的 Formal Adapter。正式 Core 的 `RequestGate`、`IntentCompiler`、`DataCatalogBuilder`、`DateRangeResolver`、`MovementResolver`、`RequirementMapper`、`ExportPlanValidator` 和现有只读 Executor 继续作为正式权威。Lab 只贡献窄 `SemanticHint` 的候选提示协议、Provider 配置思想和失败关闭测试思想。

正式目标调用链应为：

```text
用户自然语言
  → RequestGate / IntentCompiler 确定性解析
  → 正式 DataCatalog / CapabilityRegistry 生成候选
  → 仅有残余歧义时调用窄 SemanticHint Provider
  → SemanticHint Validator
  → 确定性 Request/Export Plan 组装
  → 正式 Validator 与 source snapshot 校验
  → 只读 Preview
  → 用户确认
  → 重新确定性组装、重新校验
  → 现有 Export Executor
```

模型不读取正式数据，不生成最终 `ExportPlan`，不决定日期、movement identity、Notes 最终范围、Raw 权限、status、confirmation 或执行动作。

## 审查基线与当前状态

| 项目 | 事实 |
|---|---|
| 分支 | `feat/local-semantic-request-interpreter-lab` |
| 当前 HEAD | `a089c85b906690ddad8f5f2c9bc9fb9e1c9df406` (`perf: tune narrow semantic hint candidate`) |
| Lab 性能候选 | Qwen2.5 0.5B GGUF，CUDA，GPU layers=99，threads=4，threads_batch=2，ctx=4096，n_predict=640，temperature=0，top_k=1 |
| Lab 候选验证 | 5/5 Hint 合法、5/5 Draft exact，中位 8.35 秒，最大 9.42 秒 |
| `main` | `0a189162d42cb2b95903d64e9a1d614df00cfe16` |
| `origin/main` | `0a189162d42cb2b95903d64e9a1d614df00cfe16` |
| Worktree | 初始审查时 clean；本轮仅新增本报告 |
| 正式状态 | `project_status.py --write --json` 报告正式 Tracker/Movement Dictionary 无 Git drift；本轮未读取其业务内容、未写入正式目录 |

本轮也阅读了正式实验索引。旧的 Custom Daily Metric Pilot 仍为 reviewed/paused，不能作为本次集成基线；未来正式任务必须以当时最新 `main` 和兼容性清单为准。

## 正式 Core 实际接口

### 已存在的正式职责

| 层 | 正式接口/文件 | 当前职责 | 对集成的意义 |
|---|---|---|---|
| 请求协议 | `fitness_ledger_core/analysis_export_request.py`、`schemas/analysis_export_request_v1.schema.json` | 校验 `request_version/purpose/datasets/notes_scope/raw/output`，限制 dataset、fields、time mode、filters 和 Notes scope；不读数据、不执行 | 是正式结构化请求协议，不应被 Lab `RequestDraft` 替代 |
| 请求门 | `request_gate.py` | 在模型前拒绝写入、计划生成、Raw，识别空请求、日期缺口和 movement 歧义 | 应保留为第一道安全门 |
| 确定性解析 | `intent_compiler.py`、`query_scope.py` | 生成 `AnalysisExportCommand`、`DeterministicRequestFacts`、`QueryScope`；绑定领域、scope operation、日期表面、Notes 层和 movement mention | 是正式语义权威，Lab 不得覆盖其结果 |
| 数据/能力目录 | `data_catalog.py`、`analysis_foundation.py` | 从正式 View、Tracker、Movement Dictionary 构建只读 snapshot、ModuleCard、MovementCard、Notes/CandidateRecord；`CapabilityRegistryV1/V2` 维护能力词汇 | 未来候选池必须由此生成，不能使用 Lab 合成 catalog |
| 时间 | `DateRangeResolver` | 解析 explicit/relative/all available 等意图，基于可用范围生成 requested/resolved window 和 warnings | 日期不进入模型可控字段；确认后仍由此解析 |
| movement | `MovementResolver`、`movement_target_scope.py`、`QueryScopeResolver` | 用正式 canonical ID、alias、body-part metadata 和 score 解析动作；歧义保留并要求选择 | 模型最多排序已有候选，不能创造 movement ID/name |
| 需求映射 | `analysis_foundation.py::RequirementMapper` | 只映射 Registry 中的能力；Notes 可要求确认；Raw 不可由模型选择 | 是 SemanticHint 与正式能力目录之间的主要适配点 |
| Plan 组装 | `intent_compiler.py::IntentCompiler.compile`、`export_plan_assembler.py` | 从确定性事实/候选包和受限 selection 生成 `ExportPlanDraft` | 对应 Lab `DraftAssembler`，但正式实现应保持唯一 |
| Plan 校验 | `export_plan_validator.py` | 校验 module、field、window、movement/note/record ID、Raw boundary、budget，并可校验 source snapshot | 是最终计划的正式安全边界 |
| Preview | `analysis_preview_service.py::AnalysisPreviewService.preview` | Gate → planner → mapping → deterministic compile → validator，`execution.allowed=false`、`executor_called=false` | 这是受控预览目标，但目前未直接成为 Web intelligent 入口 |
| 执行 | `intelligent_export.py::ExportExecutor` | 在已验证计划和 package 上重新校验 source snapshot，调用只读 View 物化输出 | 只能在明确用户确认后的正式边界调用；本轮不调用 |
| Web 导出 | `web_desktop/backend/server.py`、`frontend/app.js` | `/api/analysis-export` 是手工日期范围导出；`/api/intelligent-export/preview` 当前调用 `IntelligentExportService.run`；前端当前标识为 deterministic/no model | 不能直接把 Lab Provider 接到现有 `run` 并宣称完成 Preview→Confirm→Execute |

### 一个必须先处理的现有差异

`AnalysisPreviewService.preview` 的契约明确是 read-only preview，不调用 Executor；但 Web 后端的 `intelligent_export_preview()` 当前调用 `self.intelligent_export.run(...)`。当前 `IntelligentExportService.run()` 是确定性单入口，但其最后会调用 `self.executor.execute(...)`，因而不是用户确认前的纯 Preview。

因此正式集成不得沿用这个方法名和旧调用语义作为最终链路。新分支必须先定义明确的 `preview` 与 `confirm/execute` 边界：

1. 自然语言请求先进入只读 Preview，响应中不包含已物化的正式导出结果。
2. 用户确认只提交确定性 confirmation token、日期 window、movement ID 或 Notes scope 等允许字段。
3. 确定性 Core 重新组装并重新验证；source snapshot 变化则拒绝旧确认并要求重新 Preview。
4. 只有确认后的独立入口才能调用现有 `ExportExecutor`。

这项边界修复属于后续正式集成，不在当前 Lab 分支实施。

## Lab 与正式接口对照

| Lab 组件 | Lab 语义 | 正式近似接口 | 结论 |
|---|---|---|---|
| `DeterministicIntent` | route/status、dataset、time、scope、requested information、Notes、missing confirmation 的中间结果 | `AnalysisExportCommand` + `DeterministicRequestFacts` + `QueryScope` + `IntentSpec` | 设计可复用；正式代码不得引入第二套 status/date/movement 事实源 |
| `SemanticHint` | 仅 `candidates` 与 `ambiguities`；candidate 有 dimension、canonical value、evidence、confidence | 正式没有同形窄 Hint；最近的是 `CapabilityRegistry`、`RequirementMapper` 及 Shadow Planner 的 model-facing requirement | 只复用边界思想；需要 Formal Adapter，不能把 Lab Hint 直接当正式 Requirement 或 Plan |
| `DraftAssembler` | 将 intent、可选 hint、confirmation 组装为最终 Lab `RequestDraft` | `IntentCompiler.compile` + `ExportPlanAssembler.assemble` | 正式必须只有一个确定性组装链；可移植测试，不复制实现 |
| Lab `RequestDraft` | Lab 自有 schema，面向匿名合成 catalog 的 dataset 结构 | `AnalysisExportRequestV1`、`ExportPlanDraft`、`ValidatedExportPlan` | 不兼容，不直接转换字段；需显式版本化 adapter |
| Lab Validator / grounding gate | 候选池/evidence、受保护字段和只读 compile 的安全校验 | `RequestGate`、`IntentSemanticValidator`、`RequirementMapper`、`ExportPlanValidator`、`validate_source_snapshot` | 正式 Validator 保持最终权威；Lab 校验不能降低正式约束 |
| `InferenceProvider` / `RuntimeConfig` | Provider 抽象、ModelProfile、llama.cpp CLI、D 盘外置参数 | `LocalModelAdapter`、实验性 `ShadowTransport` | 只复用 Provider/配置分工；不得改共享 Ollama 或全局模型配置 |
| Lab CLI/evaluator | 独立 Gold、匿名摘要和窄模型回归 | 正式 `tools/*_test.py`、Preview/Web service 测试 | 仅作为迁移测试来源；不把 Lab Gold 成绩当正式产品成绩 |

## 可复用与不可复用清单

### 可直接复用的设计原则

- 窄 `SemanticHint` 顶层只有 `candidates` 和 `ambiguities`。
- candidate 必须绑定正式允许的 dimension、canonical value、原文 evidence 和 confidence；重复、未知 dimension、池外值、无 evidence 一律拒绝。
- 确定性层已经完成的字段设置 protected fence，Hint 不能覆盖 status、dataset、日期、次数、scope、relation、Notes 最终范围或 confirmation。
- Provider 不可用、超时、非零退出、空输出、非法 JSON、非法 Hint 均 fail-closed。
- 先判断是否需要 Hint；明确请求和 unsupported 请求不调用模型。
- 性能候选配置只作为窄 Hint Provider 的外置候选，不成为全局模型配置。
- 评测只保存匿名结构化摘要，不保存 Prompt、stdout、推理过程或正式数据。

### 必须改造后复用的部分

- **能力目录**：从 Lab synthetic `data/capability_catalog.json` 改为正式 `CapabilityRegistryV1/V2` 与 `DataCatalogBuilder` 生成的 request-scoped candidates。
- **时间**：Lab 的 `time_intent` 不能直接进入正式计划；通过 `DateRangeResolver` 生成候选窗口，日期完整性和确认由 `RequestGate`/正式 Core 决定。
- **动作和部位**：Lab canonicalization 只能作为测试思路；正式值必须来自 `MovementResolver`、`QueryScopeResolver`、`MovementTargetScopeResolver` 和正式字典 metadata。
- **Notes**：Lab Notes 类型/范围必须映射为正式 `notes_context` 与允许的 `daily/diet/training/movement` scope；不确定时进入 confirmation，不能由模型决定。
- **requested information**：由正式 `AnalysisExportCommand` 的 domain/layer、Registry capability 和 registered task/evidence layer 共同确定；Hint 只能在既有候选中排序。
- **组装与校验**：使用正式 `IntentCompiler.compile`、`ExportPlanAssembler` 和 `ExportPlanValidator`，而不是复制 Lab `DraftAssembler` 形成第二个正式计划生成器。
- **Provider**：需要一个受控 formal adapter，将窄 Hint 请求转换为现有正式本地模型接口可接受的调用；Provider 仍只能接收匿名候选，不接收正式 record/raw content。

### 不应进入正式代码的部分

- Lab `RequestDraft` schema、Lab `core.py` 的独立 dataset 表达和 synthetic catalog。
- Lab 完整 Draft `infer()`、旧完整 Draft prompt 或任何让模型直接产生最终 RequestDraft/ExportPlan 的旁路。
- Lab Gold 原句、案例编号和逐案答案。
- 任何把 0.5B 配置写入共享 Ollama、全局工具模型或正式业务配置的改动。
- 任何在模型层暴露 Raw、正式 record ID、正式 Notes 文本、真实日期范围或可执行字段的实现。
- 任何绕过 `RequestGate`、`DateRangeResolver`、`MovementResolver`、`ExportPlanValidator` 或 source snapshot 的兼容入口。

## 正式 catalog 替换与字段映射

正式适配器应使用以下映射；这些是能力/字段的设计映射，不是把 Lab catalog 文件复制进正式代码：

| Lab dimension/dataset | 正式 capability | 正式模块/字段来源 | 模型可选范围 |
|---|---|---|---|
| `body` / body state | `body_history` | `DataCatalogBuilder` body module；正式 request fields 由 `DATASET_FIELDS["body"]` 约束 | 只能在确定性 body candidate 中排序 |
| `diet` | `diet_macros` | diet module；`date/calories_kcal/protein_g/carbs_g/fat_g/food_summary` | 只能在已允许字段/能力中排序 |
| `training` | `training_context` | training module；`date/split/standardized_summary` | 只能在已允许字段/能力中排序 |
| `movement_progress` | `movement_progress` | formal movement history/progress cards、MovementResolver canonical IDs | 模型不得创建或改写 movement ID |
| Notes | `notes_context` | `DataCatalogBuilder.notes`、formal note candidates、Notes scope parser | scope 不确定必须 confirmation |
| Raw | `raw_trace` | formal raw entries / request parser / validator / executor | `model_selectable=False`，不进入 Hint candidate pool |

字段的正式版本来源必须同时记录：

- `analysis_export_request_v1` / `REQUEST_SCHEMA_VERSION`：正式请求协议；
- `REGISTRY_SCHEMA_VERSION`：能力 ID、model-selectable、confirmation、Raw grant 属性；
- `REQUIREMENT_SCHEMA_VERSION` 与 `MAPPING_SCHEMA_VERSION`：Requirement/Mapping 契约；
- `ExportPlanDraft`/`ValidatedExportPlan` 的现有 plan/schema 版本；
- 新 adapter 应有独立版本，例如 `fitness-ledger-local-semantic-hint-adapter-v1`，不能把 Lab schema version 冒充正式 schema version。

失败行为必须按正式事实分类：

| 失败 | 正式结果 |
|---|---|
| catalog、Tracker/Dictionary snapshot 或 schema 不可用 | `mapping_unavailable` 或 safe fallback；不调用模型或不产生 plan |
| 未知 capability/field/movement/note/record ID | Validator error；无 plan、无 compile、无执行 |
| 日期不完整/范围冲突 | `clarification_required`；不由 Hint 填日期 |
| movement 不唯一 | `movement_resolution_required`；Hint 只能排序已给候选，最终由用户选 |
| Notes scope 未明确 | `clarification_required` 或 `notes_context` confirmation；模型不得授予范围 |
| Raw、写入、删除、同步、训练计划 | Gate 在模型前拒绝，分别保持 `raw_permission_required`/`unsupported_operation` 等状态 |
| Provider 不可用或 Hint 非法 | `model_unavailable`/`planner_invalid`；没有最终 Draft/Plan、没有 compile/Executor |
| source snapshot 变化 | `SOURCE_CHANGED`；旧确认失效，要求重新 Preview |

## 最小集成边界

后续正式实现只应增加一个边界适配器：

```text
Formal RequestGate/IntentCompiler
  → Formal candidate projection (CapabilityRegistry + DataCatalog cards)
  → Narrow SemanticHint request/response adapter
  → IntentCompiler / ExportPlanAssembler
  → ExportPlanValidator + source snapshot
  → read-only Preview
```

### 模型实际可见内容

模型只接收经过投影的匿名输入：

- 用户请求中仍需解释的残余表述，限于必要语义表面；
- 已由正式 Core 生成的候选 `dimension`、canonical label/value、短 evidence 表面和允许的候选 ID；
- protected dimensions 的摘要，明确禁止覆盖；
- Hint schema、候选池和 ambiguity 输出约束。

模型不得接收正式 Tracker/Notes/Raw 文本、正式日期值、可执行 Plan 字段、正式 record ID，除非未来审查证明某个匿名稳定 ID 是安全且必要的；默认不接收。

### Provider 与 0.5B 配置

Qwen2.5 0.5B 只作为该窄 Hint Provider 的候选配置：

- `ModelProfile`、模型路径、llama.cpp 路径、CUDA/GPU layers、timeout、threads、context 和采样参数继续外置；
- 默认不改正式全局模型配置；
- 不调用、停止、重启或修改共享 Ollama，也不占用 11434；
- 模型路径缺失、运行时缺失、超时、非零退出、空输出或 Hint 校验失败时，返回安全确认/失败状态，不复用上一轮 Hint；
- Provider 失败时不生成正式 Draft、不生成 Plan、不进入 compile 和 Executor。

正式集成第一版不新增 `llama-server` Provider。若未来确有常驻进程需求，应另开性能/运行时审查，使用独立端口、独立进程所有权、健康检查、超时和明确关闭，不影响现有 CLI Provider。

## 用户确认设计

| 缺口 | Preview 展示 | 用户提交 | 重新进入的确定性步骤 |
|---|---|---|---|
| movement 不唯一 | 正式 canonical display name、body part、候选说明/证据；不展示未验证值 | 选择一个已有 movement ID，或明确放弃 | `MovementTargetScopeResolver` → `IntentCompiler.compile` |
| body part 对应多个动作 | body-part 级范围与可选动作候选 | 选择 body-part 保持聚合，或选择已有动作 | 正式 resolver → plan assembly |
| 日期/相对训练关系不完整 | 可用窗口、anchor、requested/resolved 语义、warnings | 选择合法 window/anchor，不能输入任意模型日期 | `DateRangeResolver` → compiler → validator |
| Notes 范围不明确 | `daily/diet/training/movement` 允许 scope 及其解释 | 选择一个或多个正式 scope | `RequirementMapper` → notes mapping → validator |
| requested information 候选排序仍不明确 | 候选 label、evidence、影响范围、confidence；ambiguity 显式保留 | 选择候选或继续收窄问题 | deterministic mapping → plan assembly |
| 缺少分析目标/必要字段 | 缺口和不会自动补全的字段 | 补充自然语言或确认项 | 从 Gate 重新开始；不让模型补缺 |

确认结果只能是上述受限 ID、scope、window 或用户文本补充；模型不替用户确认。确认后必须重新运行确定性解析、能力映射、Plan Validator 和 source snapshot 校验，不能把 Preview 中间结果直接当作执行授权。

## 当前 Web/桌面入口与集成影响

- `/api/analysis-export` 当前是手工日期范围的本地 Markdown/JSON 导出，不应被 SemanticHint 改写。
- `/api/intelligent-export/preview` 当前前端作为 “DETERMINISTIC REVIEW / NO MODEL” 入口，但后端实际调用 `IntelligentExportService.run`；该方法会完成 Executor 物化，和用户要求的“Preview → 用户确认 → Executor”不一致。
- `AnalysisPreviewService.preview` 已有更接近目标的 read-only response，明确 `execution.allowed=false` 和 `executor_called=false`，但它目前使用独立 Shadow Planner/transport 契约，且不是当前 Web 后端的 intelligent endpoint 实现。
- 现有 `shadow_planner.py` 固定使用共享 Ollama `qwen3:4b`/11434 的实验性边界。本轮不调用或修改它，也不把 Lab Provider 直接替换进去。

因此未来 Web 接入顺序应为：先建立正式 preview DTO 与确认 DTO，再将窄 Hint 适配器接入只读 Preview；确认执行必须新增清晰的授权边界。当前 UI 的手工导出入口保持不变。

## 预计实施文件、测试与提交

以下是后续新分支的估算，不是本轮实际修改清单。

### 预计文件

新增或改造约 8–12 个文件：

- 新增正式 adapter/DTO，例如 `fitness_ledger_core/local_semantic_hint_adapter.py` 与 `fitness_ledger_core/analysis_semantic_hint_bridge.py`；
- 新增 formal candidate projection/confirmation DTO（可合并到 adapter，避免过度拆分）；
- 只在确认 API 设计完成后小幅修改 `analysis_preview_service.py`；
- 只在后端契约稳定后修改 `web_desktop/backend/server.py`；
- UI 仅新增 confirmation/preview 展示，不改现有手工 Export；
- 新增 `tools/local_semantic_hint_adapter_test.py`、confirmation/preview tests、匿名 formal fixture tests；
- 新增一份 formal integration contract/compatibility note。

### 预计测试

最低约 36 个新断言，目标 40–45 个：

- 10–12 个 catalog/capability/field/version mapping；
- 8–10 个 movement/date/Notes confirmation；
- 8–10 个 SemanticHint validation、protected field、pool/evidence 失败关闭；
- 6–8 个 Provider unavailable/invalid output/no cache/no bypass；
- 8–10 个 Preview → confirmation → reassembly → source snapshot/Executor boundary；
- 1 个 Web endpoint contract 和 1 个 anonymous response redaction audit。

另外增加至少 18 条与正式 catalog 对齐的匿名 E2E 案例，覆盖明确请求、多 Dataset、movement/body_part、相对训练日期、Notes、模糊/缺失、Raw/写入越权、Provider 不可用和非法 Hint。Lab 30 Gold 继续作为 Lab 回归，不能替代这些正式匿名案例。

### 建议提交计划

1. 本提交：Lab 分支的 Stage F 设计报告，冻结候选证据。
2. 新分支 Commit F1：正式 adapter、版本化 DTO、formal catalog projection、确定性失败关闭和单元测试。
3. F2：只读 Preview 与用户 confirmation boundary，补集成测试；必要时接入 Web backend，但不接 Executor。
4. F3：确认后的现有 Executor 边界、source snapshot revalidation、Web/E2E 回归和安全审查。每个提交独立可审查，不 Push、不直接合并 `main`。

## 数据、权限和运行时风险

1. **真实数据泄露**：`DataCatalogBuilder` 能看到正式 Tracker/Dictionary，CandidateRecord/Notes/Raw 结构必须在进入 Provider 前重新投影和审计；默认模型输入不得含 Notes 原文、Raw、真实记录内容或正式日期值。
2. **movement 身份越权**：label 相似不等于 identity。只接受正式 resolver 已给的 canonical ID，低分或多匹配必须用户确认。
3. **时间误导**：模型不能解释成最终日期。日期 window、anchor、可用范围和 source snapshot 必须由正式 resolver 决定。
4. **Notes/Raw 权限扩张**：Notes scope 不是模型 confidence；Raw capability 明确 `model_selectable=False` 且 `grants_raw=True`，必须在 Gate 和 Validator 双重阻断。
5. **执行时陈旧**：Preview 后数据可能变化；确认执行前必须重新校验 source snapshot，失败则重新 Preview。
6. **现有入口语义混淆**：当前 Web intelligent-preview 名称与实际 `run()`/Executor 行为不完全一致，未修正前不接 Lab Provider。
7. **共享运行时污染**：0.5B 路径只在外置、隔离的 llama.cpp CLI Provider 配置中存在；不改 Ollama、11434、其他工具或全局模型。
8. **结果审计污染**：正式响应只保留匿名的 route、candidate 摘要、validation/status、latency 和 error category；不得保存 Prompt、stdout、推理过程或正式数据摘录。

## 端到端验收门槛

在新正式集成分支上，以下条件必须全部满足才可考虑候选进入产品评审：

### 功能与职责

- Lab 30 Gold 仍为 `ready=20 / needs_confirmation=6 / unsupported=4`，但明确标为 Lab regression；
- 新增至少 18 条 formal catalog 匿名案例，按正式 capability、field、movement ID、time window 和 Notes scope 验证；
- 明确请求、multi-dataset、movement/body_part、相对训练日期、Notes、模糊/缺失、Raw/写入请求全部得到确定性预期状态；
- 20 条 ready 类案例的正式 Request/Plan 字段 exact，confirmation 类不得猜测，unsupported 类不调用模型；
- Provider 只处理残余 ambiguity；明确确定性请求和 Gate 拒绝请求 Provider 调用为 0；
- SemanticHint 合法率、candidate pool 内率、evidence 合法率均 100%；任何非法 Hint 都无 Plan；
- Preview 前 `Executor` 调用、写入、Raw 物化和正式导出均为 0；确认后只允许现有 Executor，且 fresh snapshot 校验通过；
- Provider 不可用、超时、空输出、非法 JSON、池外值、无 evidence、未知 dimension、protected-field overwrite 均 fail-closed；不复用缓存；
- legacy complete-Draft `infer()`/旧 planner 不在新活动路径可达，测试证明调用次数为 0。

### 安全与回归

- Raw 越权、写入、Executor 越权、正式数据访问旁路在 Preview 阶段均为 0；
- `RequestGate`、`DateRangeResolver`、`MovementResolver`、`RequirementMapper`、`ExportPlanValidator` 和 source snapshot 测试全部通过；
- Web preview 返回匿名、版本化 DTO，不含 Prompt、stdout、正式 Notes/Raw 或模型自由字段；
- 全部正式 Core 相关测试、Lab 30 Gold、Python compile、`git diff --check` 通过；
- 性能只作为辅助指标，不以 Lab 8.35 秒直接承诺正式产品性能；需在正式 catalog、正式 preview DTO 和实际 UI 流程中重新测量。

## 分支与封存决定

本 Lab 候选应先以当前提交 `a089c85` 为实验候选封存，保留 `reports/stage_e_model_benchmark.md` 和本报告作为证据。不要把 Lab 分支整体合并到 `main`，不要把 Lab synthetic catalog、RequestDraft 或完整 Draft 代码复制到正式 Core。

建议随后从独立 `feat/formal-local-semantic-hint-integration` 分支/Worktree 受控引入，仅实现正式 adapter 和测试；集成分支完成上述门槛后再进行独立 review。即使未来接入成功，0.5B 也只属于窄 SemanticHint Provider 的候选配置，不是共享 Ollama、全局模型或正式业务能力的替代品。

本轮状态：**设计完成；尚未满足正式产品接入或发布条件；可以开始新分支的受控 adapter 实施。**
