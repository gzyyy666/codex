# Complex Set + Session Superset 产品体验改动报告

日期：2026-09-11
范围：候选工作区 `codex/complex-set-superset-20260911`
结论：`COMPLETED_THIS_ROUND`（候选 / review，不代表正式发布）

## 1. 这轮改动给用户带来的结果

用户可以在同一条训练记录里完成以下闭环：

1. 在 Daily Entry 输入普通组、Complex Set 和明确的 Superset 关系。
2. 在 Parse & Review 中看到复杂组的连续 segment、动作编号和超级组关系，并在保存前修正。
3. 保存后，胸、肩等多个已存在 Session Theme 都能看到同一个完整 training session，而不是生成拆开的半个 session。
4. 在 Movement Progress 查看某个动作时，能知道它属于哪个超级组、处于超级组第几个动作，并直接查看同组其他动作的组数据。
5. 在 PWA 的 session 详情中，用适合触摸的展开控件看到同样的必要关系信息。

本轮特别补齐了之前的交互缺口：桌面端过去只有点击弹窗；现在鼠标悬停或键盘聚焦关系条会出现轻量详情卡，点击仍保留为完整详情和触摸 fallback。

## 2. “超级组作为一个小 session”的产品定义

可以这样理解，但只在阅读和交互层成立：

- 对用户：超级组是当前 training session 里的一个“小 session / 局部训练单元”，有自己的成员列表、组内顺序和每个动作的组数据。
- 对系统：它不是第二个 `training_session`，也不是新的 movement。真实 session 仍只有一个，超级组只是 `organization_relations[]` 中的一条关系。
- 对统计：同组动作不会因为展示关系而重复计数、重复计算 volume 或改变动作身份。Complex Set 的 segment 仍属于一个 Set，不能被当成多组普通 Set。

因此界面使用“小 session · 组内顺序”作为帮助理解的语言，但不会制造新的 session id。这样既满足训练时的阅读心智，也保持历史、导出和统计的单一事实来源。

## 3. 各产品路径的体验变化

### 3.1 Daily Entry → Review → Save

LLM 和用户输入的建议格式是 ASCII 半角、完整 Daily Entry 文本：

```text
2099-01-06
training: 胸肩
1. Incline Press
(7.5+5)-(6+8)-3
2. Triceps Pushdown
30kg x 12 x 3
superset: A = movement 1, movement 2
```

其中：

- `(7.5+5)-(6+8)-3` 表示一个动作的一个 Complex Set：每组连续执行 `7.5×6 + 5×8`，共 3 组。
- `superset: A = movement 1, movement 2` 是独立关系行；动作仍按编号独立保存，不能把两个动作合并成一个动作。
- LLM 被明确要求输出一份可直接粘贴的完整文本、使用半角标点、保留动作编号和关系行；只有用户明确表达超级组时才输出关系，不从相邻动作猜测。
- 复制用户的裸片段（例如 `3. y举` 加全角数字/括号/连接符）时，输入层会做标点归一化并进入 Review，不再误判成创建 Data Module 字段。

未知动作或未知主题仍不被猜测：动作会进入 Review 供用户选择“新增动作 / 映射已有动作 / 仅保留原始记录”；不存在的 Session Theme 不会被静默创建，也不会阻断训练记录保存。

### 3.2 Session Theme Archive

一个 session 可以有多个已存在主题。以“胸肩”为例：胸主题页和肩主题页都展示同一个完整 session，包含两个动作和超级组标记。这里按主题筛选的是 session 的归属，不是把动作拆成两个 session。

如果用户输入了确实新的训练主题，当前行为是保留训练记录、显示未设置/未识别主题状态，并等待用户在主题管理中新增后再建立关系；如果只是没有录入 theme，则仍可按 session/date 查到训练记录，不丢失原始内容。

### 3.3 Movement Progress：桌面端

当某条历史动作记录属于超级组，记录卡会显示：

`超级组 A · 组内 1/2 · Triceps Pushdown`

鼠标悬停关系条时，详情卡显示：

- 当前动作处于超级组的第几位 / 总成员数；
- 按关系 canonical member 顺序排列的全部动作；
- 每个动作的 `sets_lines`，包括 Complex Set 的连续段格式。

点击关系条会打开完整详情弹窗，键盘聚焦与窄屏点击也能使用。桌面端的 hover 不是唯一入口，避免触摸设备和键盘用户被排除。

### 3.4 PWA session 详情

PWA 不依赖 hover，而是在每个动作卡下提供原生 `<details>` 展开：

- 收起态保留 `超级组 A · 第 1/2 个动作` 这一必要上下文；
- 展开态显示“小 session · 组内顺序与组数据”；
- 当前动作标记为“当前动作”，并与其他成员一起按 `#1/#2/...` 顺序列出；
- 同组动作的摘要和组数据可直接阅读，动作轨迹入口仍独立存在；
- 使用 article + 内部按钮结构，避免 button 嵌套 button，并通过窄视口横向溢出检查。

## 4. 上下游适配清单

| 环节 | 适配结果 | 用户价值 |
| --- | --- | --- |
| 输入解析 | Complex Set、全角标点、裸动作片段、Superset 关系行 | 复制/口述内容更容易进入 Review |
| Review | 复杂组按 segment 展示，关系按动作编号显示 | 保存前能发现结构错误 |
| 保存与 canonical data | `training_session` 只有一份，关系写入 `organization_relations[]` | 不重复 session、不重复统计 |
| Session Theme | 多个已存在 theme 指向同一 session | 胸、肩页面都能看到完整训练 |
| Movement Progress | 关系标签、组内顺序、hover/focus 卡、click modal | 从单动作追溯超级组上下文 |
| PWA | 关系投影、当前动作、成员顺序、tap 展开 | 手机端获取足够上下文 |
| Analysis Export | 保留 `sets`、`segments`、`set_count`、`segment_count`、`total_reps`、`volume`、`organization_relations.members` | 下游模型不会把结构关系或派生 volume 丢掉 |
| Cloud/read projections | 继续只读投影 canonical session relation | 不另造一套 PWA/云端事实 |

关系顺序来自 canonical `organization_relations.members`，而不是从页面出现顺序临时推断；展示层额外投影 `member_order` / `relation_order`，不会回写到 movement item。

## 5. 验证与 review 证据

已验证的重点包括：

- Complex Set 结构解析、全角标点归一化、segment 数量不一致拦截；
- 关系-only 变化不改变 movement 数量、组数、volume、顺序和实例身份；
- 同一 session 在胸/肩两个主题下各展示一次完整记录；
- Movement Progress 桌面端真实浏览器 hover、focus、click 详情；
- Desktop 窄视口 click fallback；
- PWA 390px 触摸展开、当前动作与同组动作组数据、无横向溢出；
- LLM entry prompt、Analysis Export、PWA/static、movement progress 相关回归。

证据截图：

- [桌面端 Movement Progress 悬停详情](C:/Users/26087/.codex/visualizations/2026/09/11/01a08fdf-80a7-7d82-9c93-1585913987bf/completion-hover-final/superset-relation-hover-desktop.png)
- [桌面端完整关系详情](C:/Users/26087/.codex/visualizations/2026/09/11/01a08fdf-80a7-7d82-9c93-1585913987bf/completion-hover-final/superset-relation-detail-desktop.png)
- [PWA 触摸展开](C:/Users/26087/.codex/visualizations/2026/09/11/01a08fdf-80a7-7d82-9c93-1585913987bf/completion-hover-pwa/superset-relation-detail-pwa.png)

## 6. 工作区与发布边界

本报告和实现只在候选工作区完成，当前目标是人工 review。没有修改正式目录 `D:\FitnessLedger\app`，没有写入正式训练数据，没有 merge、push、tag、部署或真实 CloudBase 上传。候选镜像可通过：

`http://127.0.0.1:8770/#movements`

复核桌面端 Movement Progress；PWA 关系详情使用候选 PWA 测试 fixture 验证。正式产品仍需经过独立封板授权和正式回归后才能发布。
