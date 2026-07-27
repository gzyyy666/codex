# Stage B：Grounded Semantic Hints

## Scope

基于 `f5aa7ba feat: add deterministic intent routing`，本轮只处理 Stage A 之后的 G20 requested-information 残余歧义。没有修改 Gold、完整 Draft Prompt、RequestDraft Schema、模型或运行时路线。

## SemanticHint contract

顶层只允许两个键：

```json
{
  "candidates": [],
  "ambiguities": []
}
```

每个 candidate 只允许：`dimension`、`canonical_value`、`evidence`、`confidence`。ambiguity 只允许：`dimension`、`reason`、`evidence`。

模型实际可见的是：用户原文、确定性层固定约束、由 capability catalog 筛出的 candidate pool、以及每个 dimension 允许的 evidence。固定约束包括 dataset、日期/天数、scope、relation、Notes 和候选维度；没有完整 RequestDraft Schema，也没有写入、Raw、Executor 或正式数据字段。

## Candidate/evidence boundary

- `dimension` 必须来自当前请求的 `requested_information.training` 或 `requested_information.diet`。
- `canonical_value` 必须来自对应 dataset 的 capability catalog 候选池。
- `evidence` 必须同时来自确定性提供的 evidence options，并且是用户原文的精确子串。
- confidence 必须在 `[0, 1]`；重复 candidate、未知 dimension、候选池外值和无 evidence 值均拒绝。
- llama.cpp 调用前还会把当前候选池编译为临时枚举 grammar；临时文件使用 ASCII JSON，调用结束立即删除。Validator 仍是最终安全边界。
- 模型无法控制 status、dataset、日期/次数、scope、relation、Notes、confirmation、Raw、Executor、write 或正式数据访问。

## Actual G20 validated SemanticHint summary

本摘要来自当前 7B CUDA 路径的一次真实 Hint 调用；只保存经过 Validator 的结构化结果，不保存 Prompt、原始 stdout 或推理过程。

```json
{
  "top_level_keys": ["candidates", "ambiguities"],
  "candidates": [
    {"dimension":"requested_information.training","canonical_value":"date","evidence":"训练","confidence":1.0},
    {"dimension":"requested_information.training","canonical_value":"session","evidence":"训练","confidence":1.0},
    {"dimension":"requested_information.training","canonical_value":"movements","evidence":"训练","confidence":0.95},
    {"dimension":"requested_information.training","canonical_value":"sets","evidence":"训练","confidence":0.9},
    {"dimension":"requested_information.diet","canonical_value":"date","evidence":"饮食","confidence":1.0},
    {"dimension":"requested_information.diet","canonical_value":"energy","evidence":"饮食","confidence":1.0},
    {"dimension":"requested_information.diet","canonical_value":"protein","evidence":"饮食","confidence":0.95},
    {"dimension":"requested_information.diet","canonical_value":"carbohydrate","evidence":"饮食","confidence":0.9},
    {"dimension":"requested_information.diet","canonical_value":"fat","evidence":"饮食","confidence":0.85}
  ],
  "ambiguities": [
    {"dimension":"requested_information.training","reason":"movements 和 sets 的具体含义不明确","evidence":"训练"}
  ]
}
```

由于两个 required dimension 的候选均完整且 confidence 均不低于 ready 阈值，ambiguity 不能单独改变最终 status；它不会覆盖确定性约束。若 ambiguity 同时伴随缺失维度，或候选不完整/置信度不足，组装器返回 `needs_confirmation`；Hint 无效或 Provider 失败则返回错误且不生成 Draft。

真实 G20 smoke 最终结果：`ready`；训练 requested information exact 为 `date/session/movements/sets`，饮食 exact 为 `date/energy/protein/carbohydrate/fat`；time 均为最近 30 天，scope/Notes/relation/status 未被模型覆盖；compiled execution 仍为 `allowed=false`、`executor_called=false`、`write_allowed=false`、`raw=false`。耗时约 118.2 秒。

## 30-case routing

- 29/30（G01–G19、G21–G30）保持 Stage A deterministic route，Provider 调用 0。
- G20 唯一进入 `infer_semantic_hint()`；旧完整 Draft `infer()` 调用 0。
- 使用 Provider spy 的 30 条路由评测：deterministic 29、Provider 1；29 条 deterministic status exact，G20 使用合法 Hint 时为 `ready`。
- 实际模型 smoke 仅运行 G20，没有重新运行完整 30 条模型评测。

## Safety and tests

新增/修改测试覆盖：合法 candidate、confidence 排序、ambiguity、unknown/protected dimension、候选池外 canonical value、evidence 不在原文、重复 candidate、完整 Draft 旁路拒绝、超时/非法 JSON、G20 组装和 29 条 Provider 跳过。

结果：22/22 单元测试通过；Python 编译检查通过；`git diff --check` 通过。一次真实模型返回候选池外 canonical/evidence 时均被 fail-closed 拒绝，未生成 Draft。

## Stage C handoff

Stage C 仍需把更多 Hint 维度接入确定性 Draft Assembler，并完成完整 30 条真实模型回归；本轮没有扩大 SemanticHint 权限，也没有处理完整 Draft 的语义准确率或性能问题。
