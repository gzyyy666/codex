# 阶段 A：确定性显式信息提取与能力边界判断

日期：2026-07-27

基线：`18af98b refactor: pluginize local inference runtime`、`c79ce51 docs: analyze Gold failures and split semantic roles`

本阶段不修改 Prompt、Schema、Gold、模型或 Semantic Hint 结构。

## 实际修改

- `deterministic.py`：新增 `DeterministicIntent`、中文/阿拉伯数字解析、日期/相对时间提取、Dataset/scope/field/Notes canonicalization、能力边界路由和 Draft 中间结果。
- `core.py`：在 Provider 之前增加确定性预路由；确定性结果仍经过现有 Validator 和 grounding gate；只有 `route=provider` 才进入原 Provider。
- `__init__.py`：导出确定性中间表示和解析入口。
- `tests/test_lab.py`：新增数字、Gold 确定性子集、unsupported/confirmation 路由、Provider 跳过和 G20 fallback 路由测试。

未修改 `prompt_v1.txt`、`schema/`、`data/gold_cases.json`、运行层配置或模型文件。

## 确定性流程

```text
user_text
  -> capability boundary check
  -> DeterministicIntent extraction
       -> unsupported: empty datasets + unsupported
       -> missing explicit information: empty datasets + needs_confirmation
       -> explicit complete intent: deterministic Draft
       -> semantic field selection pattern: existing Provider fallback
  -> existing Validator
  -> existing grounding gate
  -> existing read-only Adapter (ready only)
```

确定性层不调用模型，也不产生 Raw、Executor、写入、正式数据路径或训练计划能力。

## Canonicalization 与边界规则

- 数字：支持阿拉伯数字，以及常见中文数字“一、二、两、三、十四”等。
- 时间：支持 `YYYY-MM-DD 到 YYYY-MM-DD`、最近 N 天、最近 N 次、前 N 天和每次目标事件前的饮食窗口。
- scope：使用 catalog 中的 body part、split、movement 词典做 canonical value；例如胸→`chest`、拉训练→`pull`、卧推→`bench_press`。
- requested information：按 Dataset capability catalog 中的字段词典抽取；未出现字段时只使用通用上下文默认字段，不从单个 Gold 原句复制答案。
- Notes：只接受显式饮食、训练、动作或每日 Notes 范围；“一些笔记”没有范围时必须确认。
- relation：由训练 target 与 preceding diet 的结构化关系确定，不由模型生成。
- unsupported：Raw/原文、训练计划/安排、修改/写入、正式 tracker/本地 tracker 访问直接返回 `unsupported`。

实现中没有 Gold 案例编号、原句全文匹配或逐案例答案分支。

## 30 条确定性路由评测

评测使用 `gold_cases.json`，Provider 使用计数桩，只验证是否路由到 Provider，不调用真实模型。

| 案例 | 期望状态 | 确定性路由 | Provider 调用 | 结果 |
|---|---|---|---:|---|
| G01 | ready | deterministic | 否 | exact ready |
| G02 | ready | deterministic | 否 | exact ready |
| G03 | ready | deterministic | 否 | exact ready |
| G04 | ready | deterministic | 否 | exact ready |
| G05 | ready | deterministic | 否 | exact ready |
| G06 | ready | deterministic | 否 | exact ready |
| G07 | ready | deterministic | 否 | exact ready |
| G08 | ready | deterministic | 否 | exact ready |
| G09 | ready | deterministic | 否 | exact ready |
| G10 | ready | deterministic | 否 | exact ready |
| G11 | ready | deterministic | 否 | exact ready |
| G12 | ready | deterministic | 否 | exact ready |
| G13 | ready | deterministic | 否 | exact ready |
| G14 | ready | deterministic | 否 | exact ready |
| G15 | ready | deterministic | 否 | exact ready |
| G16 | ready | deterministic | 否 | exact ready |
| G17 | ready | deterministic | 否 | exact ready |
| G18 | ready | deterministic | 否 | exact ready |
| G19 | ready | deterministic | 否 | exact ready |
| G20 | ready | provider fallback | 是 | 阶段 B 保留；本阶段不要求 ready |
| G21 | needs_confirmation | deterministic | 否 | exact confirmation |
| G22 | needs_confirmation | deterministic | 否 | exact confirmation |
| G23 | needs_confirmation | deterministic | 否 | exact confirmation |
| G24 | needs_confirmation | deterministic | 否 | exact confirmation |
| G25 | needs_confirmation | deterministic | 否 | exact confirmation |
| G26 | needs_confirmation | deterministic | 否 | exact confirmation |
| G27 | unsupported | deterministic | 否 | exact unsupported |
| G28 | unsupported | deterministic | 否 | exact unsupported |
| G29 | unsupported | deterministic | 否 | exact unsupported |
| G30 | unsupported | deterministic | 否 | exact unsupported |

### 路由统计

| 指标 | 结果 |
|---|---:|
| 案例总数 | 30 |
| Provider 跳过 | 29/30（96.7%） |
| Provider fallback | 1/30（G20） |
| G01–G19 exact ready | 19/19 |
| G21–G26 exact needs_confirmation | 6/6 |
| G27–G30 exact unsupported | 4/4 |
| 阶段 A 范围内状态准确率 | 29/29 |
| Raw 越权 | 0 |
| Executor 调用 | 0 |
| 写入能力 | 0 |
| 正式数据访问 | 0 |

G20 使用 Provider fallback 是通用规则：当训练和饮食都明确、存在分析/比较目标、时间为宽泛月份但 requested information 未显式出现时，阶段 A 不猜字段，保留给阶段 B Semantic Hint。不是对 G20 原文或编号的特殊判断。

### 确定性 ready 子集字段准确率

在 G01–G19 上，以下字段均为 19/19（100%）：

- status
- dataset selection
- time intent
- scope
- requested information
- Notes scope
- relation
- confirmation

## 测试与检查

- Lab 单元测试：**19/19 passed**。
- 新增测试覆盖：中文数字、阿拉伯数字、日期范围、最近次数、前后关系、Notes canonicalization、scope/split/movement 同义词、unsupported 边界、缺失字段确认、确定性成功跳过 Provider、G20 fallback 路由。
- Python 编译检查：通过。
- `git diff --check`：通过。
- 未运行完整 30 条真实 7B 推理评测；本轮路由评测使用 Provider spy，避免重新消耗模型时间。

## 仍未解决的问题

- G20 的训练/饮食 requested information 语境选择仍交给阶段 B，不在本阶段猜测。
- 现有 7B 完整 Gold 基线仍为 1/30，平均约 91.8 秒，P95 约 117.3 秒；本阶段没有重新包装或声称改善模型语义准确率/性能。
- 当前旧评测报告没有保存逐案原始 Draft；阶段 C 需要补充逐案 Hint、Draft、错误和延迟保存，才能完成更强的根因归因。
