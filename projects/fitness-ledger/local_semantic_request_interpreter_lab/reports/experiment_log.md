# Experiment Log

## Baseline and environment

- 时间：2026-07-27 Asia/Hong_Kong
- Worktree：`C:\Users\26087\Documents\github-memory-worktrees\fl-local-semantic-request-interpreter-lab`
- 分支：`feat/local-semantic-request-interpreter-lab`
- 基线 HEAD：`7d93b4cf979bc0a3a2fec3118689fdc813ec2f5b`
- `main` / `origin/main`：`0a189162d42cb2b95903d64e9a1d614df00cfe16`
- 硬件：Windows 11；RAM 15.74 GB；NVIDIA GeForce RTX 4060 Laptop GPU，4 GB；C: 剩余约 6.97 GB；D: 剩余约 137.88 GB
- Python：3.14.6；本机起始时没有 `jsonschema`、`pydantic`、`outlines`、`transformers`、`torch`、`llama_cpp` 或 `lmformatenforcer`
- 共享服务：Ollama 可用，已有 `qwen3:4b`；本实验尚未调用共享 Ollama

## Commands

| 阶段 | 工作目录 | 命令 | 结果 |
|---|---|---|---|
| baseline | Lab root | `git status --short --branch` | clean；分支和 SHA 匹配 |
| environment | Lab root | `python --version` | Python 3.14.6 |
| source runtime | Lab root | 官方 b10142 Windows CPU zip 下载、解压；`llama-cli.exe --version` | 成功；version 10142，commit `3d1c3a897` |
| schema/validator | `projects/fitness-ledger` | `python -m unittest discover -s local_semantic_request_interpreter_lab/tests -v` | 5/5 passed |
| gold inventory | `projects/fitness-ledger` | JSON UTF-8 读取 `data/gold_cases.json` | 30 cases |
| model candidate | D runtime | Qwen2.5 1.5B GGUF 下载 | 因网络速度在 15 分钟超时，保留为未完成临时文件；未使用 |
| model candidate | D runtime | Qwen2.5 0.5B GGUF 下载 | 进行中；未调用共享 Ollama |
| structured smoke | D runtime | 官方 `json_schema_to_grammar.py` 生成 GBNF；`llama-cli --grammar-file` | 成功生成并解析 `{"status":"ready","count":1}` |
| model probe | D runtime | Qwen2.5 0.5B，单轮目标请求 | JSON 生成不完整或语义字段错误；Validator 拒绝 |
| model candidate | D runtime | Qwen2.5 1.5B GGUF，断点续传完成 | 1,117,320,736 bytes；SHA-256 `6A1A2EB6D15622BF3C96857206351BA97E1AF16C30D7A74EE38970E434E9407E` |
| model probe | D runtime | Qwen2.5 1.5B，目标请求和简单饮食请求 | JSON 可完整生成，但关系/Notes/scope 语义错误；Validator 拒绝 |
| fixed baseline | D runtime | Qwen2.5 0.5B，30 Gold，单并发 | mean 14,350.49 ms；P95 16,544.76 ms；安全 Raw overreach 0，但语义闭环 0/30 |
| CUDA runtime | D runtime | 官方 b10142 `llama-b10142-bin-win-cuda-12.4-x64.zip`；`llama-cuda\llama-cli.exe --version` | 成功；`ggml-cuda.dll` 存在；未使用共享 Ollama |
| model candidate | D runtime | Qwen2.5 7B Instruct GGUF Q4_K_M 两分片 | 4,683,073,632 bytes；Apache-2.0；与 CUDA 12.4 独立运行 |
| target acceptance | D runtime | Qwen2.5 7B + `--n-gpu-layers 99` + grammar + grounding | 成功：`status=ready`；训练最近三次胸训；饮食 before_each_target_event 3 天；关系正确；compiled execution disabled |
| fixed Gold evaluation | D runtime | Qwen2.5 7B + CUDA，30 Gold，单并发 | 完成；全部语义字段闭环 1/30；Raw 越权 0/30；mean 91,815.20 ms；P95 117,308.95 ms；结果状态 `ready=12`、`needs_confirmation=11`、`invalid_model_output=7` |

## Safety observations

- 未读取正式 tracker、正式 movement dictionary 或正式 Notes 正文。
- 未读取或提交模型文件、虚拟环境、缓存和推理输出。
- 未停止、重启或修改 Ollama；未修改 qwen3:4b、全局配置或其他工具。
- 当前组件没有 Executor、写入、删除、同步或 Raw 权限接口。
- 0.5B 固定集保留在 `runs/baseline_eval.json`（被 Git 忽略）；所有 30 条均保留失败行。
- 7B 目标成功原始结果保留在 D 盘 `runs/qwen7b_cuda_target6.stdout.txt`；正式报告只保存摘要，不提交模型和原始运行输出。
- 7B 固定 Gold 报告保留在 Lab 的 Git 忽略路径 `runs/qwen7b_cuda_eval.json`；摘要已写入阶段报告，不提交模型和原始运行输出。
