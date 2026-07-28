# Intelligent Export Local Analysis — 人工 Review Evidence

Review 基线：`fe9eb27b0870d04043ec01da72ecfeb6f2d63907`

本文件和同目录的
[`evidence/analysis_preview_review_evidence.json`](evidence/analysis_preview_review_evidence.json)
是人工 Review 成品。JSON 由
[`tools/analysis_preview_review_evidence.py`](../../tools/analysis_preview_review_evidence.py)
使用匿名 fixture 生成；不读取正式 tracker，不保存真实 Notes 正文，不执行正式 Command。

## 1. 结论先行

最初产品目标已经在“只读 Preview 阶段”实现：

```text
自然语言目标
  → deterministic RequestGate
  → 合法分析才进入 qwen3:4b Planner
  → AnalysisRequirementSpec
  → RequirementMapper
  → IntentCompiler / DateRangeResolver / MovementResolver
  → ExportPlanValidator
  → GPTAnalysisPackage 只读 Preview
  → 人工查看、编辑、确认
```

当前候选没有实现正式 Web 接线，也没有实现正式 GPT 分析生成或正式导出执行。这是有意保留的 Review 停止点。

Review 判断：`READY_FOR_WEB_PREVIEW_REVIEW` 仍然成立。

## 2. 现场复核

| 项目 | 结果 |
|---|---|
| Worktree | `C:\Users\26087\Documents\github-memory-worktrees\fl-intelligent-export-local-analysis-pipeline` |
| Branch | `feat/intelligent-export-local-analysis-pipeline` |
| HEAD | `fe9eb27b0870d04043ec01da72ecfeb6f2d63907` |
| Worktree | clean |
| main / origin/main | `0a189162d42cb2b95903d64e9a1d614df00cfe16` / 相同 |
| Web Integration Worktree | clean，HEAD `527791f27d87b1961c06455fc2a3fe358bd09c3c` |
| Executor | Preview Service 不持有、不调用 Executor |
| 正式数据 | 未写入；测试只使用匿名临时 fixture |

`fe9eb27` 完整包含上一轮 5 个候选文件。本轮只增加 Review 文档、匿名证据生成器和生成的匿名证据 JSON。

## 3. Open-source Adoption Record

本轮采用的是经过官方文档核对的架构模式，不复制第三方运行时代码，也不新增第三方依赖。

### 3.1 Semantic Router：把路由放到模型前面

- 问题：qwen3:4b 不应负责判断删除、Raw、动作歧义和缺少分析目标；模型一旦收到这些请求，就可能把“拒绝”与“能力选择”混在一起。
- 查阅：[Aurelio Semantic Router 官方文档](https://docs.aurelio.ai/semantic-router/user-guide/guides/semantic-router)；文档描述 Route Layer 消费 query 并输出 route/category。[Hybrid Router 文档](https://docs.aurelio.ai/semantic-router/user-guide/components/routers)进一步说明语义与关键词可以组合。
- 标准做法：先将输入分到有限路由，再让下游组件处理对应任务。
- Fitness Ledger 落点：`fitness_ledger_core/request_gate.py` 的 `RequestGate.evaluate()`；`ANALYSIS_REQUEST` 才能进入 `AnalysisIntentPlanner`，其它状态直接返回。
- 没有照搬：没有引入 embedding、向量索引或第三方 router。Fitness Ledger 已有闭集合 `AnalysisExportCommandParser`、`QueryScopeResolver`、`IntentCompiler.prepare()`，确定性实体和日期解析必须优先于相似度判断。
- 新变量与复核：初始全 Registry 视图运行时，复合请求出现 optional capability 过选；重新以官方 Router 的“路由先于下游选择”模式核对后，采用 Gate 维度生成 Registry v2 受控子视图。没有改 Prompt、Schema 或 Gold。

### 3.2 NeMo Guardrails：输入边界与执行边界分离

- 问题：模型输出可以是结构合法的 JSON，但仍可能越过 Raw、Notes、写入或正式计划边界。
- 查阅：[NeMo Guardrails Rail Types](https://docs.nvidia.com/nemo/guardrails/about-nemo-guardrails-library/rail-types) 和[配置文档](https://docs.nvidia.com/nemo/guardrails/configure-guardrails/yaml-schema/guardrails-configuration)。官方定义 input rails 在 LLM 前，execution rails 在 action/tool 执行前后，output rails 在返回用户前。
- 标准做法：输入安全、对话流、工具执行和输出检查分层，不让一个模型提示承担全部策略。
- Fitness Ledger 落点：输入层是 `RequestGate`；模型后是 `AnalysisRequirementSpecV1.from_dict()`、`RequirementMapper`、`ExportPlanValidator`；`GPTAnalysisPackage.build()`再次拒绝未确认 Notes 和 Raw。
- 没有照搬：没有加入 Colang、NeMo runtime 或第二个 Guardrail 模型。当前 Preview 不调用工具、不执行 Command，确定性 Core 已经是更强的执行边界。
- 新变量与复核：本地没有真实 action call，因此 execution rail 以 Validator + `executor_called=false` 证据表达；正式 Web 接入前仍需把这个状态接到后端执行授权点。

### 3.3 LangGraph：显式状态流和人工中断

- 问题：Web 端未来需要展示“已识别、待澄清、待确认、可 Preview”，不能依赖一次不可追踪的函数调用。
- 查阅：[LangGraph Overview](https://docs.langchain.com/oss/python/langgraph/overview)、[Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、[Interrupts](https://langchain-ai.github.io/langgraph/concepts/breakpoints/) 和[Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)。官方模式是显式 graph state、checkpoint、interrupt、resume 和 approve/edit/reject。
- 标准做法：把每一阶段的输入、输出、错误和人工决定作为状态，而不是隐式重试。
- Fitness Ledger 落点：`RequestGateDecision`、Preview response 的 `gate/planner/validation/resolution/review/execution/trace` 字段，以及已有 `AnalysisTrace` / `HumanCorrection` Foundation Contract。
- 没有照搬：没有引入 LangGraph dependency；本轮没有长时运行 agent，也没有 Web session/checkpoint 基础设施。加入框架反而会扩大变量。
- 新变量与复核：当前只有进程内稳定 `trace_id`，没有跨请求持久化 resume。重新对照官方 HITL 文档后确认这是 Web 接入缺口，不是假装已完成的能力。

### 3.4 Ollama Structured Outputs：模型只产出受限结构

- 问题：qwen 原始文本不能直接进入 Core；JSON 合法也不等于权限合法。
- 查阅：[Ollama Structured Outputs 官方文档](https://docs.ollama.com/capabilities/structured-outputs)。标准方式是请求时提供 JSON schema，再由应用侧用结构校验器验证。
- 标准做法：模型输出 schema 与应用验证双重约束；不把模型输出当作可执行命令。
- Fitness Ledger 落点：`OllamaShadowTransport.generate()`、现有 two-stage selection/details schema、`AnalysisRequirementSpecV1.from_dict()`、`RequirementMapper`。
- 没有照搬：没有把 Ollama tool calling 接给删除、写入、同步或 Executor；Planner 看不到任何 destructive tool。
- 新变量与复核：现有 Shadow Planner 已提供 qwen3:4b transport 和 schema，不再另造 adapter。真实 acceptance 显示平均约 12.5 秒，结构化输出可用但不适合承担安全路由。

### 3.5 Home Assistant Conversation / Intent API：明确状态给前端确认

- 问题：前端必须知道是“可 Preview”还是“需要用户补充动作/日期/权限”，而不是只收到一个空结果。
- 查阅：[Home Assistant Conversation API](https://developers.home-assistant.io/docs/intent_conversation_api/) 和[Intent Firing](https://developers.home-assistant.io/docs/intent_firing/)。标准做法是明确 intent response/status，并用 conversation id 支持后续输入。
- 标准做法：意图识别响应是协议对象，后续澄清由应用负责，不由模型自行执行。
- Fitness Ledger 落点：Service statuses `ready`、`clarification_required`、`movement_resolution_required`、`raw_permission_required`、`unsupported_operation`、`model_unavailable`、`planner_invalid`、`mapping_unavailable`；`trace_id` 和 `review.editable_fields` 为前端确认准备。
- 没有照搬：没有接入 Home Assistant conversation runtime；Fitness Ledger 的数据域、Core 和权限模型不同。
- 新变量与复核：当前没有 conversation id / resume API。对照官方 Conversation API 后将其列为后端路由接线缺口，而不是继续扩展本地 Service。

### 3.6 现有 deterministic Core：唯一执行权

- 问题：模型不能选择正式字段、记录、日期、Notes scope、Raw 或 ExportPlan。
- 现有资产：`DataCatalogBuilder`、`AnalysisExportCommandParser`、`IntentCompiler`、`DateRangeResolver`、`MovementResolver`、`CandidateSummarizer`、`ExportPlanValidator`、`ExportExecutor`、`GPTAnalysisPackage`。
- 标准做法：LLM 只产出受限意图；业务系统负责实体、权限、计划、校验和执行。
- Fitness Ledger 落点：Planner 只返回 `AnalysisRequirementSpecV1`；Core 负责 `compile()`、具体日期、动作解析、候选数据、正式 ID 和 Validator。Preview 明确不调用 `ExportExecutor`。
- 没有照搬其它框架：这些已经是项目自身可核验的业务契约，换成通用 agent/tool framework 会削弱可审计性。
- 新变量与复核：无新的执行解释器。模型越权时由 Mapping/Validator 拒绝，不做自动 Repair。

## 4. M1/M2/M3 资产处置

| 资产 | 当前处置 |
|---|---|
| M1 Foundation Registry / RequirementSpec / Mapping / GPT Package / Trace | 进入正式 Preview 候选路径 |
| M2 DataCatalog / anonymous evaluation / privacy audit | 进入 Gate、Core resolution 和 Review Evidence |
| M3 `OllamaShadowTransport` / qwen3:4b / two-stage planner | 进入合法请求 Planner；仍保持 shadow-only，不执行 Command |
| M3 `CapabilityRegistryV2` model view | 进入受控模型视图；不继续做语义微调 |
| Holdout、Grounding、Failure Classification | 保留为评测工具，不作为运行时解释器 |
| `_legacy_run()` | 不恢复、不调用 |
| Planner Repair / Assembler 路线 | 不进入本候选 Preview 路径 |
| Cloud、Mini Program、Notes audit、Custom Daily Metric | 未修改 |

停止要求 qwen3:4b 独自完成安全路由的原因是：输入分类、权限和实体歧义属于确定性业务政策；真实运行还观察到复合请求在全 Registry 视图下过选 capability。让模型自行“拒绝危险请求”既无法稳定复现，也会重复已有 Core 能力。模型现在只负责合法分析意图的结构化表达。

## 5. 九个匿名端到端案例

完整逐案例 JSON 在 `evidence/analysis_preview_review_evidence.json`。下表是人工审阅摘要；`Planner=2` 表示两个真实模型阶段，`0` 表示 Gate 或 transport 在模型前结束。

| Case | User Input | Gate | Planner | Spec | Resolution / Mapping | Package | Status | Executor / Raw / Write | Latency |
|---|---|---|---:|---|---|---|---|---|---:|
| body_recent | 分析最近体重变化 | ANALYSIS_REQUEST | 2 | body_history | recent / body_history | yes | ready | 0 / 0 / 0 | 11.526s |
| diet_recent | 分析最近饮食 | ANALYSIS_REQUEST | 2 | diet_macros | recent / diet_macros | yes | ready | 0 / 0 / 0 | 12.418s |
| training_recent | 分析最近训练 | ANALYSIS_REQUEST | 2 | training_context | recent / training_context | yes | ready | 0 / 0 / 0 | 12.125s |
| diet_training_impact | 分析饮食是否影响训练 | ANALYSIS_REQUEST | 2 | diet_macros + training_context | recent / 两项能力 | yes | ready | 0 / 0 / 0 | 14.071s |
| delete_diet | 删除最近饮食记录 | UNSUPPORTED_WRITE_OPERATION | 0 | none | none | no | unsupported_operation | 0 / 0 / 0 | 0 |
| raw_trace | 查看 Raw 原始记录 | RAW_PERMISSION_REQUIRED | 0 | none | permission gate | no | raw_permission_required | 0 / 0 / 0 | 0 |
| ambiguous_target | 看看最近情况 | CLARIFICATION_REQUIRED | 0 | none | target missing | no | clarification_required | 0 / 0 / 0 | 0 |
| ambiguous_movement | 看看推胸有没有进步 | MOVEMENT_RESOLUTION_REQUIRED | 0 | none | movement unresolved; no safe candidate | no | movement_resolution_required | 0 / 0 / 0 | 0 |
| ollama_unavailable | 分析最近体重变化 | ANALYSIS_REQUEST | 0 | none | not run | no | model_unavailable | 0 / 0 / 0 | 0 |

所有 4 个合法请求的 `AnalysisRequirementSpec` 均通过 schema、capability mapping、Core validation 和 package boundary。所有 5 个非 Planner 案例均没有模型调用。

## 6. Web-ready Request / Response Contract

未来 Web 请求只需要提交：

```json
{
  "request": "分析饮食是否影响训练",
  "budget_mode": "standard",
  "confirmations": {}
}
```

统一响应顶层字段：

```json
{
  "schema_version": "fitness-ledger-analysis-preview-service-v1",
  "status": "ready",
  "trace_id": "preview:<stable-hash>",
  "gate": {},
  "planner": {},
  "validation": {},
  "resolution": {},
  "mapping_preview": {},
  "gpt_analysis_package_preview": {},
  "review": {"required": true, "editable_fields": []},
  "execution": {"allowed": false, "mode": "preview_only", "executor_called": false},
  "trace": {}
}
```

状态示例：

```json
{
  "status": "ready",
  "gate": {"status": "ANALYSIS_REQUEST", "reason_codes": []},
  "planner": {"status": "planned", "model": "qwen3:4b", "latency_ms": 14071},
  "validation": {"status": "passed", "scope_locked_by": "deterministic_core"},
  "resolution": {"status": "resolved", "movement_ids": [], "notes_selection_count": 0},
  "gpt_analysis_package_preview": {"raw_included": false, "notes_scope": null},
  "execution": {"allowed": false, "executor_called": false}
}
```

```json
{"status":"clarification_required","gate":{"status":"CLARIFICATION_REQUIRED","reason_codes":["EMPTY_SCOPE"]},"planner":{"status":"not_run"},"execution":{"allowed":false,"executor_called":false}}
```

```json
{"status":"movement_resolution_required","gate":{"status":"MOVEMENT_RESOLUTION_REQUIRED","reason_codes":["MOVEMENT_REQUIRES_CLARIFICATION"],"movement_candidates":[]},"planner":{"status":"not_run"}}
```

```json
{"status":"raw_permission_required","gate":{"status":"RAW_PERMISSION_REQUIRED","reason_codes":["RAW_PERMISSION_REQUIRED"]},"planner":{"status":"not_run"},"gpt_analysis_package_preview":null}
```

```json
{"status":"unsupported_operation","gate":{"status":"UNSUPPORTED_WRITE_OPERATION","reason_codes":["UNSUPPORTED_OPERATION"]},"planner":{"status":"not_run"}}
```

```json
{"status":"model_unavailable","gate":{"status":"ANALYSIS_REQUEST"},"planner":{"status":"model_unavailable","error_code":"MODEL_UNAVAILABLE"},"execution":{"allowed":false,"executor_called":false}}
```

```json
{"status":"planner_invalid","planner":{"status":"planned"},"validation":{"status":"failed","error_code":"CAPABILITY_SCOPE_MISMATCH"},"execution":{"allowed":false,"executor_called":false}}
```

Web 端未来只负责提交目标、展示 Gate/范围/警告、让用户编辑或确认，再请求 Preview 或正式导出。当前仍缺：

1. 纯前端接线；
2. 后端路由接线；
3. 确认状态持久化、conversation/resume、认证和正式导出授权。

Preview Service 本身没有必须补的结构缺口；正式 Web/正式导出前的确认持久化和授权层仍是后端产品能力缺口。

## 7. Review 验证矩阵

| 验证 | 结果 |
|---|---|
| Preview Service / Gate / Fake transport | PASS |
| qwen3:4b 合法请求 acceptance | PASS，4/4 ready |
| model unavailable | PASS，0 model call |
| Raw / delete / ambiguous / movement ambiguity | PASS，全部 Gate 拦截 |
| executor_not_called | PASS，9/9 为 false |
| 正式数据零写入 | PASS，匿名临时 fixture 前后 hash 相同 |
| Foundation Contract | PASS |
| Shadow Planner Contract / Evaluation | PASS |
| Adapter / Date / Error / Query Scope | PASS |
| Python compile | PASS |
| `git diff --check` | PASS |
| Web `node --check` | N/A，本轮未修改 Web 文件 |
| `intelligent_export_core_test.py` | 基线失败，`movements[0]` 为空；未修改冻结 Core 掩盖 |
| `intelligent_export_selection_test.py` | 基线失败，deterministic `run()` 不返回旧 `selection`；未修改冻结 Core 掩盖 |
| 全量 qwen Shadow Matrix | 本轮 bounded acceptance 已通过；18-case 旧 Shadow 测试超过 124 秒超时，未伪称通过 |

## 8. 数据安全证据

- 模型上下文来自 `safe_model_context()`，不包含原始日期键、Raw 正文、正式记录正文或正式数据包。
- qwen acceptance 的 Package `raw_included=false`，Notes scope 未被模型自动确认。
- Review JSON 不包含 `private raw`、正式 tracker 路径、movement dictionary 路径或真实 Notes 正文。
- 9/9 `executor_called=false`；9/9 `formal_data_written=false`；9/9 `raw_read=false`。
- `ExportPlanValidator` 只在 Preview 中校验 Draft；`ExportExecutor` 未接入该 Service。

## 9. 人工 Review 步骤

1. 打开本文件和 `evidence/analysis_preview_review_evidence.json`，逐案例核对 Gate、Planner 次数、Spec、Validation、Mapping 和 Package 摘要。
2. 重点确认四个合法请求的能力是否与用户目标一致，尤其是 `diet_training_impact` 是否没有偷偷加入 body/movement/notes。
3. 确认四类边界请求均为 `planner.status=not_run`，且 `executor_called=false`。
4. 查看基线失败是否接受为旧 deterministic 输出契约不一致；不要通过恢复 Legacy Planner 或修改 Frozen Core 解决。
5. 如果 Review 通过，下一步才是单独规划 Web Preview endpoint、确认状态存储和前端确认 UI；本 Commit 不包含这些变更。

## 10. 本地人工测试 UI

在 `projects/fitness-ledger` 下运行：

```powershell
python tools/analysis_preview_review_ui.py --port 8788
```

然后打开 `http://127.0.0.1:8788/`。页面使用匿名临时 fixture，输入目标后可以查看 Gate、Planner 原始结构化输出、AnalysisRequirementSpec、Validation、范围、Mapping 和 GPT Package 摘要；填写人工期望能力后点击“导出匿名案例”，即可得到可提交 Review 的 JSON。

UI 只监听本机，默认使用当前 `qwen3:4b` transport；Ollama 不可用时显示 `model_unavailable`。页面没有正式数据路径、Executor、Cloud 或原 Web 页面连接。
