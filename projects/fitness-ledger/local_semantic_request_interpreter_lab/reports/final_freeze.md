# Local Semantic Request Interpreter Lab 最终冻结报告

日期：2026-07-27

## 冻结决定

Local Semantic Request Interpreter Lab 已完成候选冻结。本报告和 README 是交接状态记录，不引入新功能，不改变模型、Prompt、Schema 语义或正式活动链路。

| 项目 | 冻结事实 |
|---|---|
| 分支 | `feat/local-semantic-request-interpreter-lab` |
| 冻结前基线 | `3e5126366bf018a24659ba3444942394893f94f0` |
| Worktree | `C:\Users\26087\Documents\github-memory-worktrees\fl-local-semantic-request-interpreter-lab` |
| `main` | `0a189162d42cb2b95903d64e9a1d614df00cfe16` |
| `origin/main` | `0a189162d42cb2b95903d64e9a1d614df00cfe16` |
| 当前状态 | 候选已冻结，等待正式 JSON 导出线完成后受控集成 |
| 正式产品状态 | 未接入、未发布，不能把 Lab 结果等同于正式产品结果 |

本轮冻结 Commit 只包含交接文档更新，不修改 Lab Python 活动代码。

## Stage A–F 成果核实

提交链核实结果：

- `34167f7 feat: add local semantic request interpreter lab`
- `919363b feat: adopt grounded CUDA 7B baseline`
- `18af98b refactor: pluginize local inference runtime`
- `c79ce51 docs: analyze Gold failures and split semantic roles`
- `f5aa7ba feat: add deterministic intent routing`
- `8082cd9 feat: add grounded semantic hints`
- `9b251cf feat: finalize deterministic draft assembly`
- `1d532ee perf: measure local semantic hint latency`
- `a4b4a8e perf: record llama server comparison`
- `b430fa6 perf: benchmark local semantic hint models`
- `a089c85 perf: tune narrow semantic hint candidate`
- `3e51263 docs: prepare controlled formal integration plan`

对应成果：

1. `InferenceProvider`、`ModelProfile`、`RuntimeConfig`、llama.cpp CLI Provider 和配置优先级已建立。
2. `DeterministicIntent` 已负责明确 dataset、时间、数字、scope、requested information、Notes 和能力边界路由。
3. `SemanticHint` 已收窄为候选与 ambiguity，并具备候选池、canonical value、evidence、confidence 和 protected-field 校验。
4. `DraftAssembler` 已统一处理确定性 intent、受限 Hint 和测试形状的用户确认。
5. 30 条 Gold、G20 真实 CUDA Hint、Stage D 性能分析和 Stage E 模型/参数基准均已记录。
6. Stage F 已完成正式 JSON 导出线的接口对照、最小集成边界、确认流程和风险设计；没有把 Lab 代码接入正式 Core。

## 最终活动调用链

确定性案例：

```text
user text
  → parse_deterministic_intent
  → DeterministicIntent(route=deterministic)
  → DraftAssembler
  → RequestDraft Validator
  → grounding gate
  → read-only compile
```

残余歧义案例：

```text
user text
  → parse_deterministic_intent
  → DeterministicIntent(route=provider)
  → InferenceProvider.infer_semantic_hint
  → SemanticHint JSON/schema/candidate/evidence Validator
  → DraftAssembler
  → RequestDraft Validator
  → grounding gate
  → read-only compile
```

Provider 只返回窄 SemanticHint，不决定最终 status、dataset、时间、scope、relation、Notes 最终范围或 confirmation。失败时不生成 Draft，不执行 compile，不触碰 Raw、Executor、写入或正式数据。

## 0.5B 冻结候选

```text
model: qwen2.5-0.5b-instruct-q4_k_m.gguf
backend: cuda
gpu_layers: 99
threads: 4
threads_batch: 2
ctx_size: 4096
n_predict: 640
temperature: 0
top_k: 1
```

模型路径、llama.cpp 可执行文件和运行时 DLL 继续位于 D 盘隔离目录。`config/runtime.example.json` 保持示例/兼容配置，不将本地模型、运行时、缓存或原始推理输出加入 Git。

## Gold 与性能结果

| 结果 | 数量 |
|---|---:|
| `ready` | 20/20 |
| `needs_confirmation` | 6/6 |
| `unsupported` | 4/4 |
| 最终 status exact | 30/30 |
| Provider 跳过 | 29/30 |
| Provider 调用 | 1/30（G20） |

语义与安全结果：

- G01–G19：确定性完成，未调用 Provider，Draft 语义字段 exact。
- G20：通过受限 SemanticHint 得到 canonical requested-information candidate，最终 Draft exact。
- G21–G26：保持 `needs_confirmation`，不猜测补全。
- G27–G30：保持 `unsupported`，不进入模型。
- G20 连续 5 次：Hint 合法 5/5，Draft exact 5/5。
- G20 延迟：中位 8.35 秒，最大 9.42 秒。
- `invalid_model_output`：确定性 29 条为 0；候选回归总体无异常。
- Raw 越权、Executor 调用、write allowed、正式数据访问：均为 0。
- Legacy 完整 Draft `infer()` 活动路径调用：0。

这些是独立 Lab、合成 catalog 和只读 compile 的结果，不是正式 JSON 导出产品的正确性承诺。

## 正式集成前置条件

Lab 不整体 merge 或 cherry-pick 到 `main`。下一步必须等待正式 JSON 导出候选线完成并通过其自身审查，然后：

1. 记录正式 JSON 导出候选的精确 Commit SHA。
2. 从该精确 Commit 新建独立集成分支，例如 `feat/formal-local-semantic-hint-integration`。
3. 只受控复用 Lab 的窄 SemanticHint contract、Provider/外置运行配置和失败关闭设计。
4. 使用正式 Capability/Data Catalog、正式 movement/date/Notes resolver、正式 JSON Schema、正式 Validator 和正式导出器。
5. 先建立 Preview-only 与用户确认边界，再考虑 SemanticHint 接入。
6. Provider 不可用、Hint 非法或候选池不一致时，退回确定性确认或安全失败，不复用缓存结果。

规划中的双路径职责：

- 清晰、可完全确定的场景走本地确定性规划，不调用模型。
- 复杂、开放或残余歧义场景继续走 GPT JSON Planner/后续 SemanticHint 路径。
- 两条路径最终必须进入同一正式 JSON Schema、同一正式 Validator 和同一正式导出器，不能形成两套正式权限或输出协议。

## 冻结后禁止事项

在本分支禁止：

- 继续调模型、Prompt、grammar、temperature、top-k 或其他采样参数。
- 扩大模型职责，让模型决定最终日期、scope、relation、Notes、status、Raw 或执行计划。
- 接入正式 Tracker、Notes、Raw、Executor 或正式 JSON 导出器。
- 整体 merge 或 cherry-pick Lab 到 `main`。
- 修改共享 Ollama、`qwen3:4b`、11434 或其他工具。
- 下载模型/运行时、提交缓存、临时文件或原始推理输出。
- 为单条 Gold 添加原句匹配、案例编号或专用答案分支。

## 冻结验收清单

- [x] 全部 Lab 单元测试通过（30/30）。
- [x] Python 编译检查通过。
- [x] `git diff --check` 通过。
- [x] Worktree clean。
- [x] 模型、GGUF、llama.cpp runtime、缓存和原始推理输出未进入 Git。
- [x] Lab 源码没有正式 Tracker/Notes/Raw/Executor 导入或写入依赖。
- [x] `subprocess` 只存在于 llama.cpp Provider 和测试桩路径；活动模型调用只经过 Provider。
- [x] 共享 Ollama、正式数据、`main` 和其他开发分支未修改。

## 交接结论

本 Lab 已达到“候选冻结、停止独立开发”的状态。当前对话和 Lab Worktree 可以停止继续开发；后续工作应在正式 JSON 导出候选的精确 Commit 上新建受控集成分支，不应恢复本分支功能开发。
