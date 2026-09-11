# Complex Set + Session Superset

## Completion evidence · 2026-09-11

本报告对应候选工作区 `codex/complex-set-superset-20260911`。本轮目标是完成度证明并补齐验收清单中确实缺失的最后一公里，不改变正式数据、正式运行目录、Cloud、Git 合并边界或整体视觉架构。

## Evidence Closure

| 验收项 | 状态 | 证据与结论 |
|---|---|---|
| 多主题归档 | `ALREADY_COMPLETE_PROVEN` | 同一 canonical `training_session.id` 的 `session_theme_ids=["chest","shoulders"]` 可同时被胸、肩筛选；浏览器两处均为 1 个 session，且每处包含完整动作与超级组上下文。 |
| Complex Set 解析、保存、历史 | `ALREADY_COMPLETE_PROVEN` | `(7.5+5)-(6+8)-3` 与全角输入均保留为一个 Set、两个 segments、3 组；历史显示 `7.5kg × 6 + 5kg × 8 × 3组`，没有伪造单一重量。 |
| Superset 是纯关系上下文 | `ALREADY_COMPLETE_PROVEN` | 关系中性回归测试比较写入前后：movement count、set count、各动作 volume、session volume、order、identity 均不变。 |
| Superset 单一真相 | `ALREADY_COMPLETE_PROVEN` | canonical 只在 Session 的 `organization_relations[]` 保存关系；动作项不复制 relation。View Model 再按成员投影 `co_members`。 |
| Desktop 关系详情 | `COMPLETED_THIS_ROUND` | 历史页关系条现在是可悬停、可聚焦、可点击的小型控件；悬停直接显示组内顺序和同组组数据，点击仍打开完整详情。 |
| Narrow / touch 关系详情 | `COMPLETED_THIS_ROUND` | Desktop 窄视口点击与 PWA 触摸视口原生 `details` 展开均通过浏览器测试；无 hover 时仍能看到全部成员与组数据。 |
| Analysis Export JSON / Markdown | `COMPLETED_THIS_ROUND` | 使用当前候选的匿名 materializer 生成真实 JSON 样本；现有协议同时接受 `json` 与 `markdown`，不新增第二套导出结构。 |
| Analysis Dataset Catalog 与外部分析 LLM | `COMPLETED_THIS_ROUND` | `DATASET_FIELDS`、materializer 字段类型、动态 Analysis Catalog、初始化 prompt 和真实导出样本形成同一条链；prompt 已明确 `segments`、组数/次数/volume、`organization_relations.members` 的语义。 |
| Daily Entry 外部录入 LLM | `ALREADY_COMPLETE_PROVEN` | 当前 `fitness-ledger-llm-entry-template-v9` 已要求顶层完整 Daily Entry、动作编号顶格规则、ASCII 结构标记、Complex Set 与 Superset 独立格式、未知信息不猜。 |
| 标量消费者 | `ALREADY_COMPLETE_PROVEN` | Movement Progress、latest/previous/best、volume、图表、session summary、Analysis Export、PWA、Open Record 均读取 canonical projection；Complex Set 只在不可比较的标量 PR 路径排除，训练记录和 volume 仍保留。 |
| 正式运行发布 | `BLOCKED` | 本轮按约束不触碰 `D:\FitnessLedger\app`、正式 tracker、Cloud、merge、push、deploy、tag；这是授权边界，不是候选实现缺口。 |

## 1. Canonical 数据证明

以下是本轮浏览器 fixture 中用于证明的匿名 canonical Session 摘要：

```json
{
  "id": "session-complex-superset",
  "Date": "2099-01-05",
  "Split": "胸肩",
  "session_theme_ids": ["chest", "shoulders"],
  "movement_items": [
    {
      "movement_instance_id": "mi-press",
      "movement_id": "m_press",
      "order_in_session": 1,
      "sets": [{
        "segments": [
          {"weight": 7.5, "reps": 6},
          {"weight": 5, "reps": 8}
        ],
        "sets": 3
      }]
    },
    {
      "movement_instance_id": "mi-pushdown",
      "movement_id": "m_pushdown",
      "order_in_session": 2,
      "sets": [{"weight": 30, "reps": 12, "sets": 3}]
    }
  ],
  "organization_relations": [{
    "id": "superset:session-complex-superset:A",
    "type": "superset",
    "label": "A",
    "members": ["mi-press", "mi-pushdown"]
  }]
}
```

这里没有第二份 A 关系挂在 `mi-press` 或 `mi-pushdown` 上。`shared_view_models.LedgerViewModels.relation_context()` 根据 Session 关系和 movement instance id 只读投影同组成员；PWA 的 `trainingDayDetail` 使用相同 canonical Session，并补齐可展示的 `co_members[].sets_lines`。

多主题不是复制 Session：

```json
{
  "chest_view": {"session_ids": ["session-complex-superset"], "session_count": 1, "movement_count": 2},
  "shoulders_view": {"session_ids": ["session-complex-superset"], "session_count": 1, "movement_count": 2},
  "all_view": {"session_ids": ["session-complex-superset"], "session_count": 1, "movement_count": 2}
}
```

## 2. 关系详情交互

当前行为保持小范围：

- Desktop Movement History：`超级组 A · 组内 1/2 · Triceps Pushdown` 是可悬停、可聚焦按钮；悬停卡直接显示“当前动作 + 按组内顺序排列的全部成员 + 各自 `sets_lines`”，点击后打开现有轻量 modal 作为完整查看和触摸 fallback。
- PWA / touch：动作卡使用原生 `<details>`；`超级组 A · 第 1/2 个动作` 展开后显示当前动作和按关系顺序排列的全部成员。没有依赖 hover，也没有把 button 嵌套进 button。
- 未关联动作不出现空关系控件；未知或不完整成员不会被猜成新动作，只显示已有 canonical 信息。

浏览器证据：

- [Complex Set Review](C:/Users/26087/.codex/visualizations/2026/09/11/01a08fdf-80a7-7d82-9c93-1585913987bf/completion-final3/complex-set-review.png)
- [胸主题完整 Session](C:/Users/26087/.codex/visualizations/2026/09/11/01a08fdf-80a7-7d82-9c93-1585913987bf/completion-final3/superset-session-chest-theme.png)
- [肩主题同一 Session](C:/Users/26087/.codex/visualizations/2026/09/11/01a08fdf-80a7-7d82-9c93-1585913987bf/completion-final3/superset-session-shoulders-theme.png)
- [Desktop 关系详情](C:/Users/26087/.codex/visualizations/2026/09/11/01a08fdf-80a7-7d82-9c93-1585913987bf/completion-final3/superset-relation-detail-desktop.png)
- [Desktop 悬停关系详情](C:/Users/26087/.codex/visualizations/2026/09/11/01a08fdf-80a7-7d82-9c93-1585913987bf/completion-hover-final/superset-relation-hover-desktop.png)
- [窄视口关系详情](C:/Users/26087/.codex/visualizations/2026/09/11/01a08fdf-80a7-7d82-9c93-1585913987bf/completion-final3/superset-relation-detail-narrow.png)
- [PWA 触摸展开](C:/Users/26087/.codex/visualizations/2026/09/11/01a08fdf-80a7-7d82-9c93-1585913987bf/completion-pwa-final2/superset-relation-detail-pwa.png)

## 3. Actual Analysis Export JSON sample

下面不是手写说明，而是当前候选 `AnonymousFixtureMaterializer` 对合法 v1.1 request 的实际 materialized records 摘要。它同时覆盖 Complex Set 与 Superset 关系：

```json
[
  {
    "dataset_id": "movement",
    "type": "movement_progress",
    "date": "2099-12-30",
    "movement_id": "m_complex",
    "movement_name": "Complex Press",
    "body_part": "chest",
    "variant": "complex",
    "order": 1,
    "sets": [{"segments":[{"weight":7.5,"reps":6},{"weight":5,"reps":8}],"sets":3}],
    "segments": [[{"weight":7.5,"reps":6},{"weight":5,"reps":8}]],
    "set_count": 3,
    "segment_count": 2,
    "total_reps": 42,
    "volume": 255,
    "organization_relations": [{"id":"superset:anonymous:A","type":"superset","label":"A","members":["mi-complex","mi-row"]}]
  },
  {
    "dataset_id": "movement",
    "type": "movement_progress",
    "date": "2099-12-30",
    "movement_id": "m_row",
    "movement_name": "Superset Row",
    "body_part": "chest",
    "variant": "standard",
    "order": 2,
    "sets": [{"weight":30,"reps":12,"sets":3}],
    "segments": null,
    "set_count": 3,
    "segment_count": 1,
    "total_reps": 36,
    "volume": 1080,
    "organization_relations": [{"id":"superset:anonymous:A","type":"superset","label":"A","members":["mi-complex","mi-row"]}]
  }
]
```

普通 Superset member 的 `segments: null` 是正确的：它是普通 Set；关系不会把它伪造为 Complex Set。Complex Set 的连续阶段仍完整存在于 `sets[].segments[]`，并有明确的 `segment_count`、`total_reps`、`volume`。

同一 request 的 `output.formats: ["json", "markdown"]` 已由现有 Analysis Export Protocol 测试验证可生成两种 artifact。当前导出是只读、`raw=false`、Preview → Confirm 之后才形成；没有为本轮再造导出通道。

## 4. Catalog 与两类 LLM 提示词

### Analysis Dataset Catalog → initialization prompt → confirmed export

当前链路是：

`analysis_export_request.DATASET_FIELDS` → `AnonymousFixtureMaterializer` / Formal Read-only projection → `Analysis Export v1.1` Preview → Confirm → 初始化 prompt 说明如何读取冻结结果。

初始化 prompt 的本轮实际约束片段是：

```text
一个 segmented set 是一个 Set 内的连续 segments，不是多个普通 sets；superset 是 Session organization context，不是新 movement。
读取 movement_progress 时必须同时保留 sets、segments、set_count、segment_count、total_reps、volume 和 organization_relations.members；volume 是导出的派生训练量，不是额外的一组。
```

它还动态嵌入当前启用的 Session Theme、Movement Category、可分析 Data Module 定义和 library shape；不把个人记录写入初始化 prompt。浏览器测试实际请求 `/api/analysis-export/initialization-prompt` 与 `/api/data-modules/analysis-catalog`，验证上述字段与 catalog schema 均可取得。

### Daily Entry 外部录入 LLM

当前 v9 模板实际要求的关键片段是：

```text
training:
 1. <动作名称>
 <重量>-<次数>-<组数>

复杂组（同一个 Set 内连续执行多个 segment）使用以下精确格式：
 (7.5+5)-(6+8)-3
其中每组都是 7.5×6 + 5×8；“+”是结构连接符，不是数学加法，也不能拆成两个普通 Set。
复杂组每一个动作仍只有一个编号；不得拆成多个普通动作或伪造单一重量。

Session 内明确的超级组使用独立关系标记，不合并动作：
 superset: A = movement 1, movement 2
该行必须单独占一行；只有用户明确表达为超级组时才输出，动作仍按编号独立保留，不能从相邻动作推断。

最终只输出一份完整、可直接粘贴到 Daily Entry 输入板的纯文本 Daily Entry；
不能只输出“3. 动作名 + 组数”片段。
```

因此像 `3. y举` 加 `（7.5＋5）－（6＋8）－3` 现在会先被全角标点归一化，再按 bare numbered training snippet 进入 Review；不会再误打开“建立新的记录项” Data Module 表单。标准可识别版本仍建议由 LLM 输出完整顶层结构和 ASCII 半角标记，便于跨模型复制。

## 5. 上下游标量消费者审计

| Consumer | 普通记录 | Complex Set | Superset |
|---|---|---|---|
| Movement Progress index | 原行为不变 | 识别 movement，保留 history；不可比较时不制造 scalar PR | 关系不改变 movement index |
| latest / previous / best | 原行为不变 | latest 与 volume 保留；Complex 不参与伪造 max-weight best | 关系不参与 best 计算 |
| volume / session volume | 原行为不变 | 按各 segment × reps × sets 计算 | 成员 volume 各自计算，关系不加权 |
| charts | 原行为不变 | 图表只接收可比较 scalar；复杂记录仍在完整 history | relation 只作 context |
| session summary / Open Record | 原行为不变 | 一个动作、完整组结构 | 一个 Session、关系在 Session context |
| Analysis Export | 原字段与协议不变 | `sets`、`segments`、派生字段一并导出 | `organization_relations.members` 一并导出 |
| PWA | 原动作卡与 session 浏览不变 | summary 保留结构 | tap 展开当前动作 + 按顺序排列的全部成员和 set info |

## 6. 新 session / 缺失 theme 的处理

- 已存在 Theme：通过当前 catalog 的 id/alias 解析；同一 Session 可得到多个已存在 theme id，归档筛选用 membership，不复制 Session。
- 没有明确 Theme：不从 Split 或动作部位猜 Theme；保留一个 canonical Session，进入 ALL Records / 未命名训练路径。后续新增 Theme 不会偷偷改写历史归属。
- 确实是新 Session：先由 Preview / Review 判断是否为新的 session；同日第二次训练仍以独立 `training_session.id` 保存，不与已有 Session 合并。
- 确实是新动作：Review 中作为新动作加入或仅保留原始记录，取决于人工选择；不会因为 Superset 关系自动创建 movement。
- 新 Theme：通过 Session Theme 管理入口原子新增/启用；只影响之后的选择与导航，历史仍以已保存关系为准。

## 7. 本轮改动范围与验证

改动集中在候选：

- `fitness_ledger_core/shared_view_models.py`：关系只读投影补充 `member_order` / `member_count` / `relation_order`。
- `web_desktop/frontend/app.js` / `styles.css`：关系条显示组内顺序，hover/focus 展示轻量详情卡，click 保留完整 modal。
- `mobile_viewer/pwa/app.js` / `styles.css`：touch-friendly 原生展开和 PWA relation member projection。
- `web_desktop/backend/server.py`：分析 LLM 初始化提示词明确字段与派生量语义。
- `tools/complex_set_superset_test.py`：canonical relation single-source 与关系中性 invariant。
- `tools/complex_set_superset_browser_test.py`：Desktop、narrow viewport、Analysis prompt/catalog 真实浏览器证据。
- `tools/run_complex_set_superset_pwa_review.py` / `tools/complex_set_superset_pwa_browser_test.py`：匿名临时 PWA 触摸证据。
- `tools/run_data_module_formal_mirror.py`：将候选镜像的 build-info 标为当前候选分支，避免人工 review 时误把候选识别为旧 follow-up。

已通过：

```text
node --check web_desktop/frontend/app.js
node --check mobile_viewer/pwa/app.js
python tools/complex_set_superset_test.py
python tools/complex_set_superset_browser_test.py --output-dir <completion-final2>
python tools/complex_set_superset_pwa_browser_test.py --output <completion-pwa-final>
git diff --check
```

本轮没有修改正式目录、正式 tracker、Cloud、dirty Session Theme audit worktree，也没有 merge、push、deploy、tag。候选 mirror 继续可用于人工 review：`http://127.0.0.1:8770/#quick`。

## 8. Research / reuse note

本轮按 two-role-community-first 完成两段独立研究：Role A 关注候选边界、工作区隔离、可验证交接；Role B 关注 Superset 常见数据表达与导出形态。外部材料只作为验证背景，没有引入外部依赖或替换本地 canonical contract。常见做法也都支持“关系/成员单独表达、动作记录保留”的方向，例如 [OpenSet](https://openset.dev/)、[Workout Open Data Interchange Specification](https://github.com/aassoiants/workout-open-data-spec)、[wger routines API](https://wger.readthedocs.io/en/stable/api/routines.html)。
