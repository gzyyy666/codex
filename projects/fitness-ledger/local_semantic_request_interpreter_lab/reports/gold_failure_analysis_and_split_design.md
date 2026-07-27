# Gold 失败分析与职责拆分设计

日期：2026-07-27

基线：`18af98b refactor: pluginize local inference runtime`

本报告只分析现有实现，不修改 Prompt、Schema、Gold、模型或运行层。

## 1. 证据范围与缺口

本次读取了：

- `data/gold_cases.json`：30 条固定案例。
- `runs/qwen7b_cuda_eval.json`：Qwen2.5 7B Q4_K_M + CUDA，30 条、每条一次。
- `evaluate.py`：字段评分规则。

评测报告保存了每条案例的 `scores`、`result_status`、`errors` 和延迟，但没有保存实际模型 Draft 或原始 stdout。因此：

- `G04/G09` 的重复字段、`G07/G16/G18/G19/G23` 的 grounding 错误是直接证据。
- 其余 `ready` 案例只能依据 Gold 与字段评分组合做“主分类”，不能断言模型实际输出了哪个错误值。
- 下表的主分类是用于确定后续架构优先级的互斥诊断分桶，不是对缺失原始 Draft 的猜测性还原。

## 2. 当前基线量化

| 指标 | 当前结果 |
|---|---:|
| Gold 案例 | 30 |
| 期望状态 | `ready=20`、`needs_confirmation=6`、`unsupported=4` |
| 实际状态 | `ready=12`、`needs_confirmation=11`、`invalid_model_output=7` |
| 全部 8 项语义字段同时正确 | 1/30（G03） |
| Raw 越权 | 0/30 |
| 平均延迟 | 91,815.20 ms |
| P95 延迟 | 117,308.95 ms |

### 8 个语义字段正确率

当前 evaluator 将没有适用 Dataset 的字段按 false 计入总分，因此同时给出原始报告分母和“有 Dataset 的 20 条 ready Gold”上的适用分母。

| 字段 | 当前报告 | 有 Dataset 的适用集 |
|---|---:|---:|
| status | 17/30（56.67%） | 17/30（56.67%） |
| dataset selection | 21/30（70.00%） | 12/20（60.00%） |
| requested information | 1/30（3.33%） | 1/20（5.00%） |
| time intent | 2/30（6.67%） | 2/20（10.00%） |
| scope | 2/30（6.67%） | 2/20（10.00%） |
| relation | 21/30（70.00%） | 12/20（60.00%） |
| Notes scope | 2/30（6.67%） | 2/20（10.00%） |
| confirmation | 17/30（56.67%） | 17/30（56.67%） |

## 3. 每条案例逐字段分析

记号：`✓` 正确，`✗` 错误，`—` 由于没有可验证 Draft 或该字段对该状态不适用。字段顺序固定为：`S=status`、`D=dataset selection`、`I=requested information`、`T=time intent`、`Sc=scope`、`R=relation`、`N=Notes scope`、`C=confirmation`。

| 案例 | 期望 → 实际 | S | D | I | T | Sc | R | N | C | 主分类 | 直接证据/判断依据 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| G01 | ready → ready | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | ✗ | ✓ | 显式信息未提取 | 字段评分失败；无原始 Draft |
| G02 | ready → ready | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | ✗ | ✓ | 显式信息未提取 | 字段评分失败；无原始 Draft |
| G03 | ready → ready | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 无失败 | 唯一完整闭环案例 |
| G04 | ready → invalid_model_output | ✗ | — | — | — | — | — | — | — | 字段之间不一致 | Validator：`requested_information must not contain duplicates` |
| G05 | ready → ready | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | ✗ | ✓ | 显式信息未提取 | 多 Dataset 字段评分失败；无原始 Draft |
| G06 | ready → ready | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | ✓ | ✓ | 时间关系理解错误 | 显式日期范围的 time intent 失败 |
| G07 | ready → invalid_model_output | ✗ | — | — | — | — | — | — | — | 数据范围扩张或猜测 | grounding：`ungrounded body_part: back` |
| G08 | ready → ready | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | ✗ | ✓ | Notes 范围错误 | 文本明确要求饮食 Notes，但 Notes 与相关字段评分失败 |
| G09 | ready → invalid_model_output | ✗ | — | — | — | — | — | — | — | 字段之间不一致 | Validator：`requested_information must not contain duplicates` |
| G10 | ready → ready | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | ✗ | ✓ | 显式信息未提取 | 字段评分失败；无原始 Draft |
| G11 | ready → ready | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | ✗ | ✓ | 显式信息未提取 | 字段评分失败；无原始 Draft |
| G12 | ready → ready | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | ✗ | ✓ | 显式信息未提取 | 字段评分失败；无原始 Draft |
| G13 | ready → ready | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | ✗ | ✓ | 显式信息未提取 | 字段评分失败；无原始 Draft |
| G14 | ready → ready | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | ✓ | ✓ | 显式信息未提取 | requested/time 字段评分失败；无原始 Draft |
| G15 | ready → needs_confirmation | ✗ | — | — | — | — | — | — | ✗ | 其他：过度确认 | Gold 为明确上肢训练笔记请求，实际进入确认 |
| G16 | ready → invalid_model_output | ✗ | — | — | — | — | — | — | — | 数据范围扩张或猜测 | grounding：`ungrounded body_part: chest` |
| G17 | ready → ready | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | ✗ | ✓ | 显式信息未提取 | 字段评分失败；无原始 Draft |
| G18 | ready → invalid_model_output | ✗ | — | — | — | — | — | — | — | 数据范围扩张或猜测 | grounding：`ungrounded body_part: chest` |
| G19 | ready → invalid_model_output | ✗ | — | — | — | — | — | — | — | 同义表达未映射 | grounding：`ungrounded session count: 2`；Gold 原文使用“**两次**” |
| G20 | ready → needs_confirmation | ✗ | — | — | — | — | — | — | ✗ | 其他：过度确认 | Gold 允许由任务语境选择训练/饮食字段，实际未 ready |
| G21 | needs_confirmation → needs_confirmation | ✓ | ✓ | — | — | — | — | — | ✓ | 正确确认 | 无 Dataset；状态与确认行为正确 |
| G22 | needs_confirmation → needs_confirmation | ✓ | ✓ | — | — | — | — | — | ✓ | 正确确认 | 无 Dataset；状态与确认行为正确 |
| G23 | needs_confirmation → invalid_model_output | ✗ | — | — | — | — | — | — | — | 应确认但模型猜测 | grounding：`ungrounded session count: 3`；Gold 未给次数 |
| G24 | needs_confirmation → needs_confirmation | ✓ | ✓ | — | — | — | — | — | ✓ | 正确确认 | 未给训练次数，正确要求确认 |
| G25 | needs_confirmation → needs_confirmation | ✓ | ✓ | — | — | — | — | — | ✓ | 正确确认 | Notes 范围未指定，正确要求确认 |
| G26 | needs_confirmation → needs_confirmation | ✓ | ✓ | — | — | — | — | — | ✓ | 正确确认 | 时间交由系统决定，正确要求确认 |
| G27 | unsupported → needs_confirmation | ✗ | ✓ | — | — | — | — | — | — | 其他：能力边界策略误判 | Raw 需求未进入 Raw，但应直接 unsupported |
| G28 | unsupported → needs_confirmation | ✗ | ✓ | — | — | — | — | — | — | 其他：能力边界策略误判 | 训练计划生成超出 Lab 边界，但未直接 unsupported |
| G29 | unsupported → needs_confirmation | ✗ | ✓ | — | — | — | — | — | — | 其他：能力边界策略误判 | 写入修改请求未直接 unsupported |
| G30 | unsupported → needs_confirmation | ✗ | ✓ | — | — | — | — | — | — | 其他：能力边界策略误判 | 正式 tracker 访问请求未直接 unsupported |

## 4. 失败类别量化

以下为互斥主分类。失败池为 24 条：30 条减去 G03 完整成功和 5 条正确 `needs_confirmation`。

| 主分类 | 案例数 | 占全部 30 | 占失败池 24 |
|---|---:|---:|---:|
| 显式信息未提取 | 9 | 30.0% | 37.5% |
| 同义表达未映射 | 1 | 3.3% | 4.2% |
| 时间关系理解错误 | 1 | 3.3% | 4.2% |
| 数据范围扩张或猜测 | 3 | 10.0% | 12.5% |
| Notes 范围错误 | 1 | 3.3% | 4.2% |
| 字段之间不一致 | 2 | 6.7% | 8.3% |
| 应确认但模型猜测 | 1 | 3.3% | 4.2% |
| 其他：过度确认 | 2 | 6.7% | 8.3% |
| 其他：能力边界策略误判 | 4 | 13.3% | 16.7% |
| **失败合计** | **24** | **80.0%** | **100.0%** |

另外：G03 为完整成功 1/30（3.3%）；G21、G22、G24、G25、G26 为正确确认 5/30（16.7%）。

### 关于“JSON/运行错误”

最新报告中没有 `MODEL_TIMEOUT`、非零退出、空输出或 JSON 解码错误。7 条 `invalid_model_output` 的可见原因是：2 条重复字段 Validator 错误，5 条 grounding gate 错误。因此本次“JSON/运行错误”可证据支持的数量为 **0/30**；不能把全部 `invalid_model_output` 都归入 JSON/运行错误。

## 5. 确定性与模型职责判断

### 5.1 案例分层数量

| 分层 | 案例 | 数量 | 占比 | 说明 |
|---|---|---:|---:|---|
| 完全确定性终止 | G01–G19、G27–G30 | 23 | 76.7% | 19 条明确 ready 加 4 条明确 unsupported；不需要模型决定语义 |
| 确定性锚点 + Grounded Semantic Hint | G20 | 1 | 3.3% | Dataset/time 明确，requested information 需依据任务语境选候选 |
| 确定性提取 + 候选提示 + 用户确认 | G21–G26 | 6 | 20.0% | 缺少 Dataset、时间、数量或 Notes 范围；最终必须用户确认 |

因此：

- 可完全确定性解析并终止的案例为 **23/30（76.7%）**；其中能生成明确 `ready` Draft 的为 **19/30（63.3%）**。
- 需要“确定性 + 模型提示”的 ready 案例为 **1/30（3.3%）**；若把确认案例的候选生成也计入可选模型提示，则为 **7/30（23.3%）**。
- 必须用户确认的 Gold 案例为 **6/30（20.0%）**。

### 5.2 字段职责

| 字段/决策 | 首要负责层 | 模型是否应直接生成最终值 |
|---|---|---|
| status | 确定性解析 + 能力边界策略 | 否；由证据完整度和能力策略决定 |
| dataset selection | 确定性词典/候选生成 | 通常否；歧义时模型只排序候选 |
| requested information | 确定性字段词典；任务语境补全时 Hint | 仅在 G20 类语境中提供候选，不直接写 Draft |
| time intent | 确定性日期/数字/相对时间解析 | 不应自由猜测数量或日期 |
| scope | 确定性同义词/能力目录候选 | 只对未决同义表达给 Hint |
| relation | Draft Assembler | 否；由 target/dependent id 确定生成 |
| Notes scope | 确定性显式 Notes 词和范围 | 缺范围时进入用户确认 |
| confirmation | 确定性缺口检测 + 用户确认 | 模型不能自行清除缺口 |

### 5.3 当前真正需要模型处理的比例

当前架构让模型直接输出完整 RequestDraft 的 8 个语义字段组，架构表面负担是 **8/8（100%）**。但 Gold 证据显示，确定性提取后真正不可由规则完成的 ready 语义只有 G20 的 `requested_information` 候选：

- 在 20 条 ready Gold 中，强制模型参与的字段组上限为 **1/8（12.5%）**。
- 按全部 30 条、每条 8 个字段组粗略折算为 **1/240（0.42%）**；这个跨状态比例仅用于说明规模，不作为模型准确率指标。
- G21–G26 的模型参与应是可选候选提示，不是最终 Draft 生成；确认缺口必须由确定性层保留。

### 5.4 拆分后的模型输出规模

建议将模型输出定义为 `SemanticHint v1`，只保留两个顶层组：

1. `candidates`：带 canonical value、来源片段和置信度的候选。
2. `ambiguities`：未决维度与需要用户确认的原因。

候选内部的 `dimension/value/evidence/confidence` 是提示元数据，不是最终 RequestDraft 字段。相比当前模型直接生成的 8 个语义字段组，顶层输出由 **8 减至 2，减少 6 组（75%）**。status、time、relation、Notes 和最终 dataset 结构由确定性 Assembler 生成。

## 6. 建议的三阶段实施顺序

### 阶段 A：确定性显式信息提取

目标：

- 从用户文本提取 Dataset kind、日期/天数/次数、显式 scope、字段 token、Notes 范围。
- 用能力目录和通用同义词表做 canonicalization；不得写 Gold 原句分支。
- 先生成中间 `DeterministicIntent`，不调用模型。
- 明确 unsupported 与 needs_confirmation 的策略边界。

预计范围：5–7 个 Lab 文件，新增 15–20 个测试，1 个 commit。

量化验收：

- G01–G19 预期 19/19 可不调用模型生成 exact ready Draft。
- G27–G30 预期 4/4 可不调用模型返回 exact unsupported。
- 至少 23/30（76.7%）案例不调用模型完成终止处理。
- 确定性子集 23/23 的 status、Dataset、time、scope、requested information、Notes、relation、confirmation 全部 exact。
- Raw 越权 0/30；Executor/write 0。

### 阶段 B：Grounded Semantic Hints

目标：

- 只向模型发送确定性解析后的残余候选和受限上下文。
- 模型只输出 `candidates` 与 `ambiguities`，不再生成完整 RequestDraft。
- 禁止模型补写未在用户文本或能力目录中有证据的数量、scope、Notes 和 relation。

预计范围：4–6 个 Lab 文件，新增 10–15 个测试，1 个 commit。

量化验收：

- 模型顶层字段由 8 组降至 2 组，减少 75%。
- 20 条 ready Gold 的 Hint canonical candidate 准确率目标 ≥90%；G20 的 requested-information 候选必须 exact。
- 6 条确认 Gold 的 needs_confirmation 判定目标 6/6；模型不得把缺口变为 ready。
- Hint 输出结构有效率 ≥95%，无 Raw/Executor/write 字段。
- 在当前单请求 CLI 运行方式下，平均/P95 不得高于基线 91.8s/117.3s；不把性能改进作为本阶段语义验收。

### 阶段 C：Draft Assembler 与回归评测

目标：

- 将 DeterministicIntent、SemanticHint 和用户确认结果合并成最终 Draft。
- relation、status、confirmation、unsupported 均由确定性逻辑完成。
- 重跑全部 30 条 Gold，保存逐案实际 Draft、Hint、errors 和 latency，弥补当前原始输出缺口。

预计范围：3–5 个 Lab 文件，新增 10–15 个测试，1 个 commit。

量化验收：

- 初始门槛：完整语义闭环至少 27/30；最终 ready/needs_confirmation/unsupported 状态 30/30 exact。
- 各字段：ready 20 条的 dataset、requested information、time、scope、relation、Notes 至少 18/20，发布门槛 20/20。
- `invalid_model_output` ≤2/30；若失败，必须无 Draft、无 compile。
- Raw 越权 0/30；Executor/write 0/30。
- 平均延迟 ≤91.8s，P95 ≤117.3s；若不改变运行技术路线，不要求本阶段承诺低于基线。
- 与当前基线明确对比：完整闭环从 1/30 提升至至少 27/30，且安全指标不回归。

## 7. 后续修改规模与提交计划

| 阶段 | 预计修改文件数 | 新增测试数 | Commit 数 |
|---|---:|---:|---:|
| 阶段 A | 5–7 | 15–20 | 1 |
| 阶段 B | 4–6 | 10–15 | 1 |
| 阶段 C | 3–5 | 10–15 | 1 |
| **合计（去重后估计）** | **9–14** | **35–50** | **3** |

本轮只提交本分析报告，不进入上述代码实施阶段。当前 7B 语义准确率和 91.8 秒平均延迟问题保持未处理。
