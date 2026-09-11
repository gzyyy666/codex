# PWA 复杂组与超级组显示修复：产品体验 Review

日期：2026-09-11
范围：独立候选工作区 `codex/pwa-display-fix-20260911`
状态：已完成本地候选修复，等待人工 Review；未合并、未 Push、未部署正式环境。

## 结论

截图中的异常不是复杂组解析失败。Web 端与 PWA 都读取同一份训练记录真相，但它们不是同一个页面的 DOM 投影，而是两条独立的只读适配链。Web 端已经能读取并展示 `segments`；PWA 的卡片格式化器此前只读取重量、次数、组数三个标量字段，因此把复杂组降级成了 `自重 × - × 3`。

本轮已让 PWA 在动作卡片中保留复杂组的完整结构，并在超级组卡片中表达“小 session”关系：

- 复杂组显示为 `7.5kg × 6 + 5kg × 8 × 3组`；
- 超级组显示组内顺序、总成员数及其他动作；
- 关系展开后显示其他成员的最近记录，例如 `Triceps Pushdown` 的 `30kg × 12 × 3`；
- 同一天存在多个 session 时，按实际 session ID 分组，不再只按日期合并；
- 下方 tabbar 仍固定在手机底部，但动作内容不再为其重复预留大块空白。

## 用户路径上的改动

### 1. 训练记录进入与解析

本轮没有改变录入词、LLM 模板或 canonical parser。已有上游结构继续作为唯一事实来源：复杂组使用 `sets[].segments[]`，超级组使用 `organization_relations` 与 `member_order`。

### 2. Web / PWA 读取适配

Web 与 PWA 都是对 canonical `TrainingSession` 的读取投影，但各自有 adapter / formatter。本轮同步补齐了：

- 本地 PWA body-area 适配器：返回 `training_session_id`、真实 session 顺序和 enriched relation context；
- 云端 `ledgerWebRead`：同样保留复杂组、超级组成员、成员顺序和同日多 session；
- Session Theme 的 PWA 读取结果：与 body-area 卡片使用相同的关系上下文；
- PWA 前端 formatter：对 `segments` 使用明确的可读串联格式，而不是尝试从复杂组读取不存在的标量 `weight / reps`。

### 3. 动作与最近表现页面

动作卡片仍然支持点击查看完整轨迹；超级组信息改为卡片内的可展开关系详情，避免用户必须离开当前动作才能理解“同组的其他动作”。关系详情不会误触发外层动作导航，并明确展示 `第 N / M 个动作`。

### 4. 手机布局

此前 `.app`、`.page` 和首页内容容器分别为固定 tabbar 预留底部空间，叠加后造成内容下沿与真实手机底边之间出现明显空白。本轮改为由可见 tabbar 统一负责底部安全区预留，普通页面使用较小的内容底距，首页保留必要的 tabbar 间距。

## 上下游影响检查

| 环节 | 本轮处理 | 影响判断 |
| --- | --- | --- |
| Daily Entry / LLM 模板 | 未改动 | 上游格式已确定，继续产生现有 canonical 结构 |
| parser / canonical TrainingSession | 未改动 | 没有改变数据契约，不需要迁移历史记录 |
| 本地 PWA adapter | 已改 | 复杂组和超级组关系现在完整到达移动卡片 |
| 云端 `ledgerWebRead` | 已改源码 | 云端部署后可获得同等读取能力；本轮未上传云函数 |
| PWA JS / CSS / HTML | 已改 | 修复格式化、关系交互和移动底部布局 |
| Service Worker | 已改 | cache 从 v53 升至 v54，资源 query 版本同步，降低旧 bundle 残留概率 |
| 导出 | 未改 | 本轮未改变导出 schema；导出继续读取 canonical `sets / segments / organization_relations` |
| 正式数据 / 正式服务 | 未改 | 未写正式数据、未重启正式服务、未部署正式版本 |

## 新 session / 新 theme 的兼容策略

- 新 session：只要进入 canonical `TrainingSession`，PWA 会按实际 session ID 展示；若没有关系数据，则作为普通动作记录展示，不虚构超级组关系。
- 新 theme：theme 由组织关系/主题读取链动态提供，不依赖固定主题枚举；未设置或尚未建立关系时，继续使用无主题/空状态，不把未知值误判为已有主题。
- 新字段：本轮采用“保留原始结构、读取端兼容缺省”的方式。旧记录没有 `segments` 或 `organization_relations` 时仍按原有普通动作路径渲染；新字段进入 canonical 后，再由各读取适配器显式传递。

## 验证证据

- canonical / 本地 PWA 投影：`tools/pwa_body_area_projection_test.py` PASS
- Session 语义回归：`tools/pwa_session_semantics_test.py` PASS
- 复杂组 + 超级组核心回归：`tools/complex_set_superset_test.py` PASS
- PWA 静态资源版本：`tools/pwa_static_test.py` PASS
- 生产 bundle 约束：`tools/pwa_production_bundle_test.py` PASS
- 本地 data-module 读取链：`tools/data_module_pwa_local_test.py` PASS
- 浏览器 body-area 视觉/交互回归：`tools/pwa_body_area_browser_test.py` PASS
- 浏览器超级组关系详情回归：`tools/complex_set_superset_pwa_browser_test.py` PASS
- `git diff --check`：PASS

人工 Review 截图：

- [body-area 复杂组与超级组 PWA 截图](../../../.codex/visualizations/2026/09/11/01a08fdf-80a7-7d82-9c93-1585913987bf/pwa-display-fix/body-area-complex-superset-pwa.png)
- [超级组关系详情 PWA 截图](../../../.codex/visualizations/2026/09/11/01a08fdf-80a7-7d82-9c93-1585913987bf/pwa-display-fix/superset-relation-detail-pwa.png)

## 发布边界

这是一份候选修复和产品体验记录。正式环境、正式云函数和其他未合并工作区均未被触碰。人工 Review 通过后，下一步才是按正式发布流程合并、推送并部署云端与桌面/手机入口。
