# Stage D1：G20 SemanticHint 性能基线与瓶颈分析

基线提交：`9b251cf feat: finalize deterministic draft assembly`

本阶段只增加匿名计时和性能观测，不改变 Gold、Prompt、Schema、SemanticHint 约束、DraftAssembler 或模型配置数值。当前活动路径仍是 CLI Provider；未启动 `llama-server`，也未访问共享 Ollama 的 11434 端口。

## 测量方法

使用当前 `runtime.example.json` 的 7B CUDA 配置，3 次均重新创建 `RuntimeBundle` 和 `LlamaCppCliProvider`，每次通过独立的 `llama-cli` 进程处理 G20。Provider 只保留数值计时、字符/令牌计数和错误码，不保存 Prompt、stdout、stderr 或推理过程。

观测阶段包括：配置与 Provider 初始化、Prompt 构建、动态 Schema 文件准备、grammar 准备、CLI 进程墙钟时间、llama.cpp 自报的模型加载/prompt eval/generation（若运行时输出）、JSON/Hint Validator、DraftAssembler、Draft Validator/grounding。当前 CLI 加 `--perf` 后没有输出可解析的模型加载、prompt eval 或 generation 行，因此这些三个字段如实记录为 `null`；CLI 进程墙钟时间包含进程启动、模型加载、prompt processing 和 token generation，不能据此把三者拆成猜测值。

## 3 次冷启动结果

| Run | 状态 / Draft exact | 总耗时 ms | CLI 进程 ms | Provider init ms | Prompt 构建 ms | Schema ms | Grammar ms | JSON+Hint ms | Assembler ms | Validator+grounding ms | 输出字符 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | ready / yes | 117930.87 | 117862.94 | 0.13 | 0.22 | 1.01 | 65.53 | 0.25 | 0.08 | 0.23 | 2536 |
| 2 | ready / yes | 114141.59 | 114073.28 | 0.08 | 0.15 | 0.49 | 66.75 | 0.11 | 0.06 | 0.10 | 2536 |
| 3 | ready / yes | 113909.64 | 113827.57 | 0.09 | 0.13 | 0.80 | 79.27 | 0.33 | 0.10 | 0.24 | 2536 |

总耗时：最小 `113909.64 ms`，中位 `114141.59 ms`，最大 `117930.87 ms`。3/3 Hint 合法、3/3 最终 Draft exact。CLI 进程墙钟占总耗时约 `99.93%`；动态 Schema + grammar 准备约 `66–80 ms`，Core 后处理小于 `1 ms`，不是瓶颈。

本次安全显存采样得到 623 个快照：显存峰值 `1508 MB / 8188 MB`，GPU 利用率峰值 `64%`。没有可复用的现有 host-process peak-RSS 采样接口，因此不伪造主存峰值；后续如需内存曲线，应另用明确的本地监控实验。

## 瓶颈判断

已证实的事实是：每次 G20 都启动新的 CLI 进程，而该进程耗时约 114 秒；配置、文件操作、grammar、Validator 和 Assembler 的耗时均为毫秒级。当前证据足以排除 Prompt 拼装、grammar 生成、JSON 校验和 DraftAssembler 作为主要瓶颈，也说明单次 CLI 调用没有模型常驻复用。

尚不能仅凭当前 CLI 输出区分 114 秒中模型加载、CUDA 初始化、prompt processing 和 token generation 的比例，因为该构建没有输出可解析的 `model_load`、`prompt eval` 或 `eval` perf 行，即使显式传入 `--perf` 也只返回最终 JSON。不能据此声称某个子阶段的精确比例。

## D2 候选与风险

最低风险且证据最充分的实验方向是：在同一 llama.cpp 运行时中，以独立端口和独立生命周期做 `llama-server` 最小 A/B，验证模型只加载一次后能否复用。运行时目录中存在 `llama-server.exe`，帮助信息支持 `--host`、`--port`、`--model`、`--grammar-file` 和 `--gpu-layers`。D1 没有启动它，也没有新增 Provider。

若 server 热调用不能保持现有动态 grammar、candidate/evidence 校验和失败关闭，则不应正式接入。若实验成功，D2 只实现可插拔的同运行时 Server Provider，并保留 CLI Provider；若未达到中位延迟至少降低 30%，则只封存数据，不宣称性能阶段成功。任何优化均需重新执行 30 条回归和至少 3 次真实 G20。

## D1 验证

计时相关单元测试与既有测试共 `30` 条，全部通过；Python 编译检查通过；`git diff --check` 通过。随后执行完整 30 条端到端回归：状态 `ready=20 / needs_confirmation=6 / unsupported=4`，Provider 调用 `1/30`，路由 `deterministic=29 / provider=1`，G20 `ready` 且字段 exact，`Raw=0 / Executor=0 / write=0 / formal_data_access=0`。本次 30 条回归总耗时统计为最小 `0.02 ms`、中位 `0.07 ms`、最大 `116444.37 ms`；P95 为 `0.56 ms`，因为仅 1 条案例需要模型，另以 G20 专项 min/median/max 作为性能指标。

D1 没有修改模型、Gold、共享 Ollama、正式数据或主线；仅增加匿名计时和本报告。
