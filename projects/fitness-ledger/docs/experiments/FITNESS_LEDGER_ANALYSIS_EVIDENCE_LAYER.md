# Fitness Ledger Analysis Evidence Layer

Current-status note (2026-07-28): this document describes the evidence-layer
experiment and its historical pre-Web boundary. The Web UI is now published
according to the product owner; do not use the old “do not connect Web” wording
as the current delivery status. The evidence layer still does not grant Raw,
write, delete, sync, or Executor authority. Read
`INTELLIGENT_EXPORT_CURRENT_STATUS.md` for the current handoff and algorithm
optimization rules.

## 目的

本层把“能力映射成功”和“拿到的数据足以回答问题”分开。它是确定性 Preview 层，不调用模型、不创建 ExportPlan、不读取 Raw、不选择 Notes scope、不调用 Executor，也不写入正式数据。

处理链为：

`RequestGate → Shadow Planner → Foundation Mapping → IntentCompiler/DateRangeResolver → Evidence Requirement Compiler → Evidence Sufficiency & Claim Validator → Package Preview`

## 当前实现映射

| 职责 | 文件 | 当前入口 |
|---|---|---|
| Gate | `fitness_ledger_core/request_gate.py` | `RequestGate.evaluate` |
| 模型候选 | `fitness_ledger_core/analysis_preview_service.py` / `shadow_planner_evaluation.py` | `AnalysisIntentPlanner.plan`、`run_two_stage_case` |
| 能力闭集合 | `analysis_foundation.py` / `shadow_planner_evaluation.py` | `CapabilityRegistryV1`、`CapabilityRegistryV2` |
| 确定性范围 | `intent_compiler.py` / `data_catalog.py` | `IntentCompiler.compile`、`DateRangeResolver.resolve` |
| 证据要求 | `analysis_evidence.py` | `EvidenceRequirementCompiler.compile` |
| 可回答性和结论边界 | `analysis_evidence.py` | `evaluate_evidence` |
| Preview 接线 | `analysis_preview_service.py` | `AnalysisPreviewService.preview` |

## 新的确定性输出

`analysis_evaluation` 是本层的权威结果：

```json
{
  "schema_version": "fitness-ledger-evidence-evaluation-v1",
  "status": "ready_with_limits | needs_confirmation | ready_for_package | insufficient_evidence | ready_for_review",
  "answerability": "ready | ready_with_limits | insufficient_evidence | needs_resolution",
  "allowed_claim_mode": "descriptive | comparative | association_hypothesis | contextual_hypothesis | multi_source_descriptive | none",
  "allowed_claims": [],
  "forbidden_claims": [],
  "missing_information": [],
  "required_next_action": "",
  "evidence_requirements": {
    "analysis_task_ids": [],
    "required_capabilities": [],
    "time_semantics": {},
    "required_confirmations": [],
    "required_fields": [],
    "recommended_fields": [],
    "required_quality_fields": [],
    "minimums": {},
    "alignment": {},
    "quality_requirements": [],
    "movement_variant_requirements": [],
    "allowed_claim_mode": "",
    "forbidden_claims": [],
    "ignored_model_derived_metrics": []
  },
  "evidence_profile": {
    "available_modules": [],
    "selected_modules": [],
    "authorized_modules": [],
    "candidate_record_count": 0,
    "materialized_record_count": null,
    "exported_record_count": null,
    "module_candidate_counts": {},
    "selected_dates_by_module": {},
    "aligned_day_count": null,
    "field_completeness": {},
    "provenance": [],
    "quality_flags": []
  }
}
```

### 计数语义

- `available_modules`：Catalog 中存在的只读模块。
- `selected_modules`：当前确定性计划选择的模块。
- `authorized_modules`：当前权限和确认状态允许进入后续包的模块；Raw 未授权不会出现。
- `candidate_record_count`：只读 Preview 阶段候选数量。
- `materialized_record_count=null`：尚未执行数据物化。
- `exported_record_count=null`：尚未执行正式导出。

旧 `date_range.record_count=0` 不再被本层作为实际记录数解释；新的 Profile 字段是当前计数语义的权威来源。

## 注册任务层

`analysis_evidence.py` 中的 `TASK_REGISTRY` 是唯一任务词汇。模型生成的 `derived_metrics` 不会直接进入 Package 或未来分析计划：

- 模型原始输出仍保留在 trace，便于审计；
- `analysis_evaluation.evidence_requirements.analysis_task_ids` 由确定性编译器生成；
- Package Preview 中 `derived_metrics=[]`、`gpt_prompt_outline=[]`；
- 未注册或自由生成的指标进入 `ignored_model_derived_metrics`，并不得执行。

## 当前匿名 Fixture 的预期结果

| 输入 | 路由状态 | 证据状态 | 原因 |
|---|---|---|---|
| 分析最近体重变化 | `ready` | `ready_with_limits` | 有 3 个候选体重点，但缺少测量条件质量字段 |
| 分析最近饮食 | `ready` | `insufficient_evidence` 或受数据日数限制 | 当前匿名 Fixture 饮食日数不足趋势最低要求 |
| 分析最近训练 | `ready` | `ready_with_limits` | 可描述训练安排/覆盖，不可自动升级为表现 |
| 分析饮食是否影响训练 | `ready` | `insufficient_evidence` | 缺少组级重量、次数、组型和足够对齐训练日 |
| 删除最近饮食记录 | `unsupported_operation` | 不运行 | Gate 在模型前拒绝 |
| 查看 Raw 原始记录 | `raw_permission_required` | 不运行 | Gate 保持 Raw 权限边界 |
| 看看最近情况 | `clarification_required` | 不运行 | 缺少分析目标 |
| 看看推胸有没有进步 | `movement_resolution_required` | 不运行 | 动作身份未唯一解析 |
| 模型不可用 | `model_unavailable` | 不运行 | fail-closed |

## 兼容策略

1. 顶层原有路由 `status`、Gate、Planner、Mapping、Execution 字段保持兼容。
2. 新的分析可回答性只新增 `analysis_evaluation` 和 `review.analysis_status`，不把旧 `ready` 误改成执行成功。
3. 原始 `analysis_requirement_spec` 仍保留在 trace，供人工审计；未来执行只能使用注册任务层和确定性 Core 结果。
4. 旧 Foundation Schema、Capability ID 和 ExportPlan/Validator 语义不改。
5. 禁止的 Raw、删除、写入、同步、正式 ID、日期和 Executor 边界继续由既有 Gate/Core 负责。

## 测试矩阵

- `tools/analysis_evidence_contract_test.py`：任务注册、计数语义、模块授权、训练摘要降级、饮食—训练证据不足。
- `tools/analysis_foundation_contract_test.py`：Foundation Schema 和权限边界。
- `tools/analysis_preview_service_test.py`：Preview 接线、Package 净化、Executor 未调用。
- `tools/analysis_preview_review_ui_test.py`：本地 UI 安全响应。
- `node --check tools/review_ui/app.js`：本地 UI JavaScript 语法。
- `python -m py_compile ...`：新增和修改 Python 文件。
- `git diff --check`：差异格式。

## 后续实施顺序

1. 用 correspondence pack 的 `request_to_requirement` 回归 Gate、能力、确认和时间语义。
2. 用 `evidence_to_claim` 回归证据充分性、结论强度和禁止结论。
3. 只有在上述确定性层稳定后，才考虑单能力请求绕过模型和复合请求减少模型调用。
4. 不在本层引入新 Capability，不接 Web 正式页面，不执行模型分析或正式导出。
