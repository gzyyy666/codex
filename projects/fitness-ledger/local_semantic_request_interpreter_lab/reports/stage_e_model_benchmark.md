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
