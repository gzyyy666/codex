# Stage E：窄 SemanticHint 模型与参数基准

基线：`9b251cf`、`1d532ee`、`a4b4a8e`

本阶段没有修改确定性路由、SemanticHint 结构、DraftAssembler、Validator、grounding gate、Gold 或正式活动链路。所有测试都使用当前 G20、同一候选池、同一动态 JSON grammar 和现有 `llama-cli` Provider；模型结果只在内存中验证，没有保存原始 Prompt、stdout、stderr 或推理过程。

## E1 固定参数

三种模型均使用：

```text
backend=cuda, gpu_layers=99, ctx_size=4096,
threads=2, threads_batch=2, n_predict=640,
temperature=0, top_k=1, llama.cpp CLI Provider
```

每个模型重新创建 Provider 并独立启动 CLI 3 次。主墙钟结果如下：

| 模型 | 逐次耗时 ms | Hint 合法 | Draft exact | 失败关闭 | 最小 / 中位 / 最大 ms | 输出字符 |
|---|---|---:|---:|---:|---:|---:|
| Qwen2.5 0.5B | 9132.83 / 8814.08 / 9087.89 | 3/3 | 3/3 | 0 | 8814.08 / 9087.89 / 9132.83 | 1913 |
| Qwen2.5 1.5B | 14037.19 / 13342.70 / 13472.61 | 3/3 | 3/3 | 0 | 13342.70 / 13472.61 / 14037.19 | 1661 |
| Qwen2.5 7B | 114197.40 / 108263.83 / 111740.00 | 3/3 | 3/3 | 0 | 108263.83 / 111740.00 / 114197.40 | 2536 |

`--verbose` 仅用于补充 llama.cpp 数值计时，未改变输入、grammar 或采样参数；随后对每个模型又各独立运行 3 次并验证 exact。诊断中三种模型 Prompt 均为 496 tokens：

| 模型 | Prompt processing 中位 / 速度 | Generated tokens | Generation 中位 / 速度 | 诊断墙钟中位 |
|---|---:|---:|---:|---:|
| Qwen2.5 0.5B | 3255.61 ms / 152.352 tok/s | 197 | 4624.11 ms / 42.603 tok/s | 9043.99 ms |
| Qwen2.5 1.5B | 6438.23 ms / 77.040 tok/s | 113 | 5436.22 ms / 20.787 tok/s | 13801.22 ms |
| Qwen2.5 7B | 30633.98 ms / 16.191 tok/s | 386 | 74384.02 ms / 5.189 tok/s | 111138.78 ms |

CPU 配置为 Windows 本地 CPU 线程配合 CUDA GPU offload；实际 GPU layers 为 99。E1 期间安全显存采样共 730 个快照，实验窗口峰值为 `1544 MB / 8188 MB`，GPU 利用率峰值 `69%`。没有使用不可靠的主存峰值估算。

## E1 结论

三种模型在窄 SemanticHint 任务上均达到 3/3 合法 Hint 和 3/3 exact Draft；0.5B 已明显优于当前 7B CLI 基线。当前最佳模型为 Qwen2.5 0.5B，固定参数中位约 9.09 秒，远低于 7B 基线约 114.14 秒。

过去完整 Draft 的失败不能等同于当前 Hint 失败。完整 Draft 需要模型同时决定 status、dataset、time、scope、relation、Notes、confirmation 等完整语义结构；当前模型只在确定性层提供的候选池中输出受限 candidate/evidence/confidence 和 ambiguity，最终语义字段仍由确定性 Assembler 生成。因此本轮重新测量的是当前窄职责，而不是复用旧完整 Draft 评测成绩。

CLI 原始 `--perf` 默认没有返回可解析的阶段计时；加 `--verbose` 后才获得上表 token 和 prompt/generation 数值。没有输出的模型加载明细被保留为空，不作推断。数据表明 7B 的主要负担是更慢的 prompt processing 和 generation；0.5B 同一 496-token Prompt 的 generation 速度约为 7B 的 8.2 倍。

## E1 安全边界

所有 E1 成功结果都经过现有 Hint Validator、Draft Validator 和 grounding gate；没有候选池外值或无效 evidence。没有调用 Raw、Executor、write 或正式数据访问能力，也没有使用缓存结果冒充当前调用。E2 参数收敛结果见本报告后续章节。

## E2 低风险参数矩阵

只对 E1 最佳的 0.5B 做小矩阵。每组只改变一个主要变量，其他参数和 grammar 保持不变；每组先运行 3 次并验证完整 Draft：

| 配置 | 变化 | 3 次结果 | 最小 / 中位 / 最大 ms |
|---|---|---:|---:|
| `base_n640_tb2` | 当前基线 | 3/3 exact | 8417.59 / 8616.24 / 8713.92 |
| `n512_tb2` | `n_predict: 640 → 512` | 3/3 exact | 8748.29 / 8762.38 / 8792.90 |
| `n640_tb4` | `threads_batch: 2 → 4` | 3/3 exact | 7480.93 / 7489.46 / 7590.77 |
| `n640_threads4` | `threads: 2 → 4` | 3/3 exact | 7327.71 / 7363.64 / 7388.53 |

`n_predict=512` 没有改善；`threads_batch=4` 有改善；`threads=4` 是本机这组低风险矩阵的最佳值。没有改 temperature、top-k、context、GPU layers、Prompt 语义或 grammar 枚举，因为当前确定性温度/候选约束已经满足准确性，且没有证据需要扩大实验面。

## E2 连续 5 次验收

最终候选配置：

```text
model=qwen2.5-0.5b-instruct-q4_k_m.gguf
backend=cuda, gpu_layers=99, ctx_size=4096
threads=4, threads_batch=2, n_predict=640
temperature=0, top_k=1
```

连续 5 次独立 CLI 冷启动结果：

| Run | Hint / Draft | 延迟 ms | 输出字符 |
|---:|---|---:|---:|
| 1 | valid / exact | 7787.80 | 1907 |
| 2 | valid / exact | 8345.77 | 1907 |
| 3 | valid / exact | 9421.30 | 1907 |
| 4 | valid / exact | 8650.78 | 1907 |
| 5 | valid / exact | 8115.60 | 1907 |

汇总：Hint 合法 `5/5`，Draft exact `5/5`，失败关闭 `0`；最小 `7787.80 ms`，中位 `8345.77 ms`，最大 `9421.30 ms`。安全显存采样 76 次，峰值 `1504 MB / 8188 MB`，GPU 利用率峰值 `47%`。一次同配置 verbose 诊断仍为 496 prompt tokens、195 generated tokens、prompt 138.005 tok/s、generation 60.626 tok/s；该诊断只记录数值，不保存原始输出。

## 候选线判定

最终 0.5B 配置同时满足：

- 最低性能候选：通过（5/5 exact，中位 ≤60 秒，最大 ≤90 秒）。
- 可交互候选：通过（中位 ≤30 秒，最大 ≤45 秒）。
- 理想候选：通过（中位 ≤15 秒，且安全与准确性保持）。

本结果说明当前窄 SemanticHint 的主要速度收益来自模型规模下降；E2 的 `threads=4` 又带来约 14.5% 的小幅改善。没有通过预填答案、缓存 Hint、删除候选/evidence 校验或绕过 Validator 获得收益。

## 回归与交付边界

E1/E2 没有修改 Python 活动代码，只增加本报告。最终验证结果：单元测试 `30/30` 通过；30 条 Gold 状态 `ready=20 / needs_confirmation=6 / unsupported=4`；路由 `deterministic=29 / provider=1`；Provider 调用 `1/30`；ready Draft 七个字段指标均 `20/20`；`invalid_model_output=0`；Raw 越权、Executor、write 和正式数据访问均为 `0`；Legacy `infer()` 活动调用 `0`。Python 编译检查和 `git diff --check` 通过。

0.5B 配置目前只是 Lab 性能候选，不自动进入正式产品，也不修改当前默认 7B 配置。进入正式产品接入仍需另开受控集成阶段，由用户明确批准后再做。
