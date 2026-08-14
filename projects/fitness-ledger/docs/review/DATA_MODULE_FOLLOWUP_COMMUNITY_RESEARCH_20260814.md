# Data Module Follow-up Community Research

日期：2026-08-14

本轮采用 two-role-community-first 的完整研究记录；研究状态文件保存在本机
临时目录 `C:\Users\26087\AppData\Local\Temp\fitness-ledger-data-module-followup-community-research-20260814.json`，并通过 Role A / Role B gate。

## 结论

选择 `EXTEND`：继续复用 Fitness Ledger 的 Data Module contract、只读
`ledgerRead` cloud function 和现有 Mini 页面，不引入外部运行时依赖。

网页审查采用 `avoid-ai-design` 的“渲染—分类—小范围修改—重新渲染”方法，
再结合项目已有 `STYLE_BIBLE.md`。没有整体安装或复制 `Hallmark`；它的流程
适合参考，但对当前存量产品过重，且社区 issue 提醒需要谨慎对待通用规则的
确定性。

## 保留的实践

1. 先看真实渲染，再判断是否有视觉问题。
2. 区分截图推断和代码确定，避免把审美猜测当成事实。
3. 保留现有 token、页面路由、数据语义和无障碍行为，优先做 surgical change。
4. 设计修改和证据记录分开，修改后在移动宽度重新审查。
5. 用项目自己的设计契约承接方法，而不是把外部 skill 整包带入。

## 候选 Mini 方案比较

| 方案 | 结果 |
| --- | --- |
| 扩展现有 `dataModuleContract.js` 与 `ledgerRead` | 采用；边界稳定、只读、可回退 |
| 小型原生 Mini component + Body/Diet/详情页适配 | 采用；不新增独立模块页面 |
| 把外部网页设计 skill 搬入 Mini | 拒绝；与数据读取运行时无关 |
| 为 Mini 新建一套平行数据协议 | 拒绝；会和桌面候选契约漂移 |

## 未做事项

- 未上传 CloudBase，未部署 `ledgerRead`，未发布 Mini。
- 未修改 `D:\FitnessLedger\app`、正式 tracker、线上数据或现有同步状态。
- 未把“去 AI 痕迹”当作自动通过条件；网页正式视觉修改仍需要下一轮截图和
  人工判断。
