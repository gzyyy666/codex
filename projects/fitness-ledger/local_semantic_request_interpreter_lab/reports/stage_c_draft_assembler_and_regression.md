# Stage C：Draft Assembler、端到端回归与候选封板

## 最终活动链路

```text
user text
  -> deterministic routing
  -> optional infer_semantic_hint()
  -> SemanticHint Validator
  -> DraftAssembler
  -> RequestDraft Validator
  -> grounding gate
  -> read-only compile
```

Core 对 deterministic route 和 provider route 都只通过 `assemble_request_draft()` 生成最终 Draft。Assembler 负责：

- 使用 `DeterministicIntent` 决定 ready、needs_confirmation、unsupported、relation、时间、scope、Notes 和安全边界。
- 仅在 provider route 接收已验证的 `SemanticHint`。
- 将确定性 candidate pool 视为 sealed set；Hint 可以提供 evidence、confidence 和排序，但不能通过省略候选缩小最终请求，也不能增加候选。
- 有效 Hint 缺少部分 sealed candidate 时仍由确定性 Assembler 生成完整 sealed 集合；Hint 不合法、无 Hint、Provider 不可用、超时、空输出或非法 JSON 均不生成 Draft。
- 测试形状的用户确认只接受 `approved + resolved_intent: DeterministicIntent`，不接受模型或任意字典直接覆盖 Draft 字段；最终仍需 Validator 和 grounding gate。

## 30 条真实端到端回归

使用当前 7B CUDA 配置运行一次完整 Gold 评测。Evaluator 对每条只保存匿名结构化摘要：route、provider_called、DeterministicIntent 摘要、验证后的 Hint 摘要、最终 Draft 摘要、status、错误码、延迟和只读 execution 摘要；没有保存用户原文、Prompt、stdout 或推理过程。

结果：

| 指标 | 结果 |
|---|---:|
| cases | 30/30 |
| ready | 20/20 |
| needs_confirmation | 6/6 |
| unsupported | 4/4 |
| Provider calls | 1/30，仅 G20 |
| deterministic route | 29/30 |
| G01–G19 字段闭环 | 19/19，各 7 个语义字段 100% |
| G20 final Draft | exact |
| G21–G26 | 6/6 needs_confirmation |
| G27–G30 | 4/4 unsupported |
| deterministic invalid_model_output | 0/29 |
| Raw 越权 | 0/30 |
| Executor 调用 | 0/30 |
| write_allowed | 0/30 |
| formal data access | 0/30 |

ready 案例字段准确率（G01–G20）为：dataset selection 20/20、requested information 20/20、time intent 20/20、scope 20/20、relation 20/20、Notes scope 20/20、confirmation 20/20。全 30 条的字段指标因 confirmation/unsupported 没有 Draft 数据集而不作为 ready 语义准确率口径；匿名评测 JSON 保留在 Lab 内 Git 忽略的 `runs/stage_c_e2e_anon.json`。

## G20 三次独立 CUDA 稳定性探针

每次新建 Provider 并独立调用，不复用上一次结果：

| Run | status | 合法 Hint | final Draft exact | latency |
|---:|---|---|---|---:|
| 1 | ready | yes | yes | 110,888.61 ms |
| 2 | ready | yes | yes | 125,496.78 ms |
| 3 | ready | yes | yes | 121,194.65 ms |

- 成功：3/3
- 合法 Hint：3/3
- final Draft exact：3/3
- 最小 / 中位数 / 最大延迟：110,888.61 / 121,194.65 / 125,496.78 ms
- 单次失败时 Core 会返回无 Draft 的失败结果；本轮未发生失败，也没有缓存复用。

## Legacy infer 审计

`LlamaCppCliProvider.infer()` 和 `LlamaJsonRunner` 为兼容旧调用保留，并明确属于 legacy 非活动接口。CLI、Evaluator 和 Core 的当前活动路径只调用 `interpret_request()`；provider route 只调用 `infer_semantic_hint()`。专项测试用只实现 legacy `infer()` 的 Provider 验证其不能到达 G20 活动路径，调用次数为 0。

源码审计确认：`subprocess` 仍只存在于 `llama_runner.py`；没有 Gold 原句、案例编号或逐案答案硬编码；没有第二套运行时、共享 Ollama、正式数据、Raw 或 Executor 旁路。

## 测试与封板结论

- 阶段 B 基线测试总数核实为 24；本轮新增阶段 C 测试后为 28/28，通过。
- Python 编译检查通过。
- `git diff --check` 通过。
- 只修改当前 Lab 目录，未修改 Prompt、Gold、共享服务、正式业务目录或 main。

候选链路已满足本轮独立 Lab 候选封板条件：统一活动链路、30/30 状态 exact、29/30 确定性跳过模型、唯一 Hint 路径真实 CUDA 3/3 稳定、失败关闭和只读安全边界均通过。

仍未处理的问题是 llama.cpp/Qwen 7B 的实际推理延迟（G20 约 111–125 秒）和模型语义任务的泛化性能。这些应另开性能/模型阶段，不应混入本候选封板提交。
