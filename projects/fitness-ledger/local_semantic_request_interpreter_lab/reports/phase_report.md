# 阶段报告：Local Semantic Request Interpreter Lab

日期：2026-07-27

## 当前状态

- 当前阶段：阶段1至阶段3已完成实验，阶段4完成一次针对性 Prompt 对照；阶段6交付物已形成，但模型尚未达到可用基线。
- 分支：`feat/local-semantic-request-interpreter-lab`
- 基线：`7d93b4cf979bc0a3a2fec3118689fdc813ec2f5b`
- 共享 Ollama：未调用；qwen3:4b 未修改；另一个工具未受影响。
- 正式数据、正式 Tracker、正式 Notes、Raw、Executor：均未访问。

## 实际采用的开源路径

`ggml-org/llama.cpp`，MIT，官方 Windows x64 CPU release b10142。实际运行官方 `json_schema_to_grammar.py`，再通过 `llama-cli --grammar-file --single-turn --simple-io` 生成结构化 JSON。官方最小案例成功：

```json
{"status":"ready","count":1}
```

模型候选为 Qwen2.5-Instruct-GGUF，Apache-2.0，运行时和模型均在 D 盘隔离目录。0.5B 完成 30 案例固定评测；1.5B 完成目标请求和简单请求探针。

## 主要结果

0.5B 固定 Gold 30 条、每条一次：

| 指标 | 结果 |
|---|---:|
| 语义闭环通过 | 0/30 |
| JSON/Validator 最终 ready/confirmation/unsupported | 0/30 |
| Raw 越权 | 0 |
| 平均延迟 | 14,350.49 ms |
| P95 延迟 | 16,544.76 ms |

主要失败类型：中文原句被放入 `requested_information`、错误猜测 body/split/movement、关系自引用、Notes 类型错误、JSON 达到 token 上限未闭合。失败输出全部进入 `invalid_model_output` 或失败关闭，不会进入 Adapter。

1.5B 在完整输出上优于 0.5B，但目标请求仍出现 Notes 结构错误，简单饮食请求仍出现自引用关系；没有证据支持把它定为正式模型。

## 安全结果

- Raw 越权率：0（固定评测中没有任何 Raw 授权路径）。
- 写入请求进入导出流程：0。
- 未知字段进入正式 Request：0；未知字段/能力值由 Validator 拒绝。
- Executor 调用：0；组件不存在 Executor 依赖。
- 共享 Ollama 影响次数：0。

## 生成的窄接口

`interpret_request(user_text, capability_catalog)` 返回版本化结果；`compile_request_draft(draft, capability_catalog)` 只产生 `preview_only`、`raw=false`、`write_allowed=false` 的编译形状。两者不包含文件路径、SQL、正式记录、写入命令或专业结论。

## 结论与后续

本阶段可以交付的是独立接口、Schema、Validator、Adapter、Gold 集、评测工具和可审计运行路径；不能交付当前 Qwen2.5 0.5B/1.5B 作为可用语义模型。下一轮应在不改变窄接口和安全边界的前提下，评估更强的本地中文结构化模型或受控模型调校；不得用大量专用 if/else 修补当前失败。
