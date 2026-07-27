# Source Adoption Matrix

检查日期：2026-07-27。来源均为项目官方 GitHub、官方示例或官方模型仓库。

| 项目 | 官方地址 | License | 维护状态 | 主要用途 | 本机实际检查/运行 | 结论 |
|---|---|---|---|---|---|---|
| ggml-org/llama.cpp | https://github.com/ggml-org/llama.cpp | MIT | 活跃；官方 Windows x64 发布包，最新 release API 返回 b10142 | 本地 GGUF 推理、JSON Schema/grammar 约束、OpenAI 风格服务 | 已下载官方 Windows x64 CPU 包；`llama-cli --version` 成功；官方 `json_schema_to_grammar.py` + `--grammar-file` 最小案例成功 | 采用主路径 |
| dottxt-ai/outlines | https://github.com/dottxt-ai/outlines | Apache-2.0 | 活跃；官方仓库显示 v1.3.0 | Pydantic/JSON Schema/regex/grammar 结构化生成，支持 Transformers、llama.cpp 等 | 读取官方 Quickstart 和模型集成说明；本机没有 Transformers、Torch 或 Outlines，未引入第二套运行时 | 暂不采用；保留作后续对照 |
| dottxt-ai/outlines-core | https://github.com/dottxt-ai/outlines-core | Apache-2.0 | 活跃；官方仓库显示 0.2.14 | JSON Schema 到 regex/FSM 的核心约束库 | 读取官方 Python/Rust 示例；需要额外 tokenizer/FSM 运行时，当前 Lab 以官方 llama.cpp 单一运行时闭环为优先 | 暂不采用；避免无必要双运行时 |
| jxnl/instructor | https://github.com/instructor-ai/instructor | MIT | 活跃；官方文档持续维护 | Pydantic 结构化提取、验证和重试，多供应商封装 | 读取官方 Ollama/本地模型支持说明；它主要提供 provider wrapper 和 validation retry，不能替代当前所需的本地 constrained decoding | 暂不采用；Validator 思路保留但不引入 provider 依赖 |
| Qwen/Qwen2.5-0.5B-Instruct-GGUF | https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF | Apache-2.0 | 官方仓库最后修改 2024-09-20 | 中文轻量本地指令模型 | 491,400,032 bytes；SHA-256 `74A4DA8C9FDBCD15BD1F6D01D621410D31C6FC00986F5EB687824E7B93D7A9DB`；30 Gold 语义闭环 0/30 | 放弃作为正式模型；仅保留基线 |
| Qwen/Qwen2.5-1.5B-Instruct-GGUF | https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF | Apache-2.0 | 官方仓库最后修改 2024-09-20 | 更强的中文本地指令模型候选 | 1,117,320,736 bytes；SHA-256 `6A1A2EB6D15622BF3C96857206351BA97E1AF16C30D7A74EE38970E434E9407E`；目标和简单请求均被 Validator 拒绝 | 暂不采用；需要更强模型或调校证据 |
| Qwen/Qwen2.5-7B-Instruct-GGUF | https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF | Apache-2.0 | 官方仓库最后修改 2024-09-20；官方分片 GGUF | 中文本地指令模型，适合更复杂的结构化语义 | Q4_K_M 两分片共 4,683,073,632 bytes；官方 llama.cpp CUDA 12.4；`--n-gpu-layers 99`；目标请求通过 RequestDraft Validator；固定 Gold 全语义闭环 1/30，Raw 越权 0/30 | 保留为当前可复现主路径，但尚未达到正式可用线 |

## 选择依据

llama.cpp 同时满足 Windows 本地独立运行、官方 GGUF 推理、JSON Schema 约束、D 盘隔离和不占用共享 11434；因此主路线来自实际安装与版本检查，而不是沿用现有 Ollama/qwen 接入便利性。Qwen2.5 0.5B 和 1.5B 都只作为隔离候选与基线，模型文件不提交 Git。
