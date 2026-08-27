# Fitness Ledger 代码重构方案

> 状态：方案待确认，未改动任何代码。
> 基线：`source/projects/fitness-ledger`，`stable_app.pyw` 6423 行 / `ledger_commands.py` 2694 行。

## 1. 现状量化

| 单元 | 规模 | 结构评价 |
| --- | --- | --- |
| `stable_app.pyw` | 6423 行 | 129 个顶层函数 + `FitnessTrackerApp(tk.Tk)` 94 个方法，God Class |
| `ledger_commands.py` | 2694 行 | `LedgerCommandService` + 异常类，结构尚可 |
| `fitness_ledger_core/` | 约 48 模块 | 已模块化（analysis / export 子系统） |

## 2. 核心问题

### P1-1 God Class + 主题代码堆叠

`FitnessTrackerApp(tk.Tk)` 同时承载 UI 装配、解析预览、数据展示、导出等全部职责。
文件内存在 4 套 UI 主题实现（themed → editorial → nike → premium），每套都各自重定义
`button` / `_surface` / `_soft_entry` / `_soft_text` / `_pill` / `_build_stream_page` 等辅助函数，
形成大量复制粘贴式堆叠。

### P1-2 死代码：同名函数重复定义（后者遮蔽前者）

Python 以模块内最后一次 `def` 为生效版本，此前同名定义为死代码。实测重复定义：

- `format_set_summary` ×5、`button` ×5、`extract_load_blocks` ×4
- `extract_training_section` ×3、`_surface` ×3
- `format_set_weight` ×2、`extract_global_notes_section` ×2、`_soft_text` ×2、
  `_soft_entry` ×2、`_pill` ×2、`_build_stream_page` ×2

另有 `_patched_*` 系列（`_patched_parse_training_movements`、`_patched_parse_entry`、
`_patched_build_data_check_page`、`_patched_refresh_data_check` 等）以「补丁式重定义」覆盖早期逻辑。
历史迭代通过「追加新定义」而非「就地修改」推进，累积了大量被遮蔽的旧实现。
**可删除规模需在阶段 1 逐段核验，不预设行数。**

### P1-3 解析逻辑双实现（架构重复，最高价值）

- `stable_app.pyw` 内有一套 UI 侧预览解析：`extract_load_blocks`、`extract_training_section`、
  `extract_cardio_metrics`、`parse_number`、`parse_date`、`extract_bowel_movement` 等。
- `ledger_commands.py` 的 `LedgerCommandService.parse()`（及 `_parse_sets_text`、
  `_prepare_generated_training_fields`）另有一套保存侧解析。

两套解析规则并行 →「预览」与「落库」可能不一致，是隐藏 bug 的温床。START_HERE.md 里
「Desktop application and parser: stable_app.pyw」与「Shared safe write boundary: ledger_commands.py」
的分工，实际演变成了双解析器。

### P2 卫生

- 换行符：`app` 与 `source` 的 `ledger_commands.py` 内容一致、仅字节差异（已归一化核验 diff=0）。
- 缓存与生成产物：本次已清理（`__pycache__`、`cloud_sync/out` 生成物、浏览器 profile）。

## 3. 目标架构

```
fitness_ledger_core/
  parsing.py              # 唯一自然语言解析器（合并 stable_app 与 ledger_commands 的解析）
  movement_dictionary.py  # 动作词典加载 / 别名 / ID / 迁移（纯函数，无 tk 依赖）
  storage.py              # JSON 读写 / 备份 / 撤销检查点（纯函数）
ledger_commands.py        # 仅保留命令服务，解析委托给 core.parsing
stable_app.pyw            # 仅保留 tk 应用装配 + 视图，目标瘦身到 ~1500 行
ui/（或 themes/）         # 主题抽象为注册表，消除 4 套复制辅助函数
```

## 4. 分阶段执行（每阶段独立提交 + 回归门禁）

- **阶段 0 · 建立基线**：跑通 `tools/regression_test.py`、`tools/smoke_test.py`、
  `tools/pwa_static_test.py` 全绿，记录 `HEAD` SHA。
- **阶段 1 · 死代码清理**：删除被遮蔽的同名旧定义与 `_patched_*` 中被覆盖的旧实现，
  仅保留最后一次生效版本。风险低，diff 大但行为不变，回归全绿即可通过。
- **阶段 2 · 抽取纯函数模块**：`movement_dictionary.py`、`storage.py`（无 tk 依赖，可单测）。
- **阶段 3 · 合并解析器**：抽到 `fitness_ledger_core/parsing.py`，`stable_app.pyw` 与
  `ledger_commands.py` 均 import 之；用测试断言「预览解析 == 保存解析」。
  **风险最高，需最高覆盖度的回归。**
- **阶段 4 · 主题注册表化**：把 themed/editorial/nike/premium 的重复辅助函数收敛为注册表 + 单套实现。
- **阶段 5 · God Class 拆分**：按页面拆 `FitnessTrackerApp` 视图方法
  （body / diet / training / movement / data_check / export）。

每阶段收尾：`git diff --check` → 对应回归 → 源/app 双端同步 → 封板前
`python tools/project_status.py --write --json` 确认 `different=[]`。

## 5. 风险与回滚

- 最高风险在阶段 3（解析合并）：预览与落库一致性是核心业务正确性，需先行补充对比测试。
- 回滚边界：Git 负责源码回退；每阶段独立提交可单独 revert；`app/data/` 全程不动。
- 硬约束：阶段 1–4 之间禁止修改 `data/tracker.json`、`data/movement_dictionary.json` 或个人云端数据。
