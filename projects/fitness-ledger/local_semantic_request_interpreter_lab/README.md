# Fitness Ledger Local Semantic Request Interpreter Lab

独立、只读、可替换的本地自然语义辅助组件。它把较明确但未完全结构化的中文数据需求转换为 `RequestDraft v1`，再由确定性 Validator 和 Adapter 处理；它不读取正式数据，不读取文件，不授予 Raw，不调用 Executor，不写入记录，也不生成健身专业结论。

## 窄接口

```python
interpret_request(user_text: str, capability_catalog: dict) -> RequestDraftResult
compile_request_draft(draft: RequestDraftResult) -> CompiledAnalysisExportRequest
```

模型输出永远先经过严格 JSON 解析、重复键拒绝、未知字段拒绝、能力目录约束、时间关系校验和只读编译。模型不可用时返回 `model_unavailable`，不产生可执行申请。

## 本地推理运行层

- `InferenceProvider`：上层唯一依赖的单请求 `infer(user_text) -> str` 抽象；保留 callable 注入兼容性。
- `ModelProfile`：模型名称、GGUF 路径和格式，不包含 CPU/CUDA 或进程参数。
- `RuntimeConfig`：Provider 名称、llama.cpp 可执行文件、CPU/CUDA、GPU layers、超时、上下文、线程和采样参数，并在启动前校验。
- `LlamaCppCliProvider`：唯一拼装 llama.cpp argv、生成 grammar 临时文件和调用子进程的实现。
- `provider_factory.py`：根据 `RuntimeConfig.provider` 创建 Provider；后续可增加实现而不改变 Core/评测器接口。

配置优先级为：显式 CLI 参数 > `--runtime-config` JSON > 兼容入口默认值。示例配置见 `config/runtime.example.json`。旧的 `--llama-cli ... --model ... --gpu-layers ...` 调用方式仍然有效；旧类名 `LlamaJsonRunner` 仅作为兼容外壳保留。

## 采用路径

本 Lab 采用官方 `ggml-org/llama.cpp` Windows x64 发行包的 `json_schema_to_grammar.py` + `llama-cli --grammar-file` 路径；最终主模型使用官方 CUDA 12.4 包。这样避免 Windows 内联 JSON Schema 参数转义问题。运行时和模型位于 D 盘的独立目录，不进入 Git，也不使用共享 Ollama 端口。

- 项目：https://github.com/ggml-org/llama.cpp
- License：MIT
- 关键官方文档：https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- JSON Schema grammar 示例：https://github.com/ggml-org/llama.cpp/blob/master/examples/json_schema_to_grammar.py
- 模型来源：https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF
- 模型 License：Apache-2.0

## 本地运行

工作目录：

```text
C:\Users\26087\Documents\github-memory-worktrees\fl-local-semantic-request-interpreter-lab\projects\fitness-ledger
```

运行标准库测试：

```powershell
python -m unittest discover -s local_semantic_request_interpreter_lab/tests -v
```

运行 CLI（模型与 llama.cpp 路径为 D 盘隔离目录）：

```powershell
python -m local_semantic_request_interpreter_lab.cli `
  --llama-cli D:\Codex\fitness-ledger-local-semantic-request-interpreter-lab-runtime\llama-cuda\llama-cli.exe `
  --model D:\Codex\fitness-ledger-local-semantic-request-interpreter-lab-runtime\models\qwen2.5-7b\qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf `
  --gpu-layers 99
```

也可以把运行参数集中放入 JSON：

```powershell
python -m local_semantic_request_interpreter_lab.cli `
  --runtime-config local_semantic_request_interpreter_lab/config/runtime.example.json
```

完整固定集评测：

```powershell
python -m local_semantic_request_interpreter_lab.evaluate `
  --llama-cli D:\Codex\fitness-ledger-local-semantic-request-interpreter-lab-runtime\llama-cuda\llama-cli.exe `
  --model D:\Codex\fitness-ledger-local-semantic-request-interpreter-lab-runtime\models\qwen2.5-7b\qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf `
  --gpu-layers 99 `
  --timeout 180 `
  --output local_semantic_request_interpreter_lab/runs/baseline.json
```

评测输出仅为匿名合成请求和模型结果，`runs/` 被忽略，不得提交模型、缓存或推理输出。

评测器与 CLI 使用同一套 `load_runtime_bundle` + Provider 工厂；本轮未重新执行完整 30 条评测。

当前实验结论：llama.cpp 的结构化生成最小示例成功；Qwen2.5 7B Q4 + CUDA 已对目标请求生成并通过 RequestDraft Validator。7B 固定 Gold 30 条的完整语义字段闭环为 1/30，说明目标句可行但尚未达到正式可用线；0.5B/1.5B 仅保留为失败对照，不能作为正式模型。

## 文件边界

- `schema/`：版本化 RequestDraft Schema。
- `data/capability_catalog.json`：合成能力说明。
- `data/gold_cases.json`：30 个固定 Gold 案例。
- `core.py`：确定性解析、Validator、Adapter 和失败关闭接口。
- `llama_runner.py`：单请求、有限超时的隔离 llama.cpp 调用。
- `evaluate.py`：固定集指标、失败行和延迟报告。
- `tests/`：安全与闭环测试。
- `reports/`：Source Adoption Matrix、命令日志和阶段报告。
