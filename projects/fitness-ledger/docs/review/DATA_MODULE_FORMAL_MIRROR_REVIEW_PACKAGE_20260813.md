# Fitness Ledger Data Module Formal Mirror Review Package

这是 Self-Service Data Module Candidate 的 Formal Web Integrated Review Mirror。它把新增记录项接入现有 Web 的 Daily Entry、Body 和 Tools 工作区，供下一轮人工体验；不是正式 Web、正式 tracker、Cloud 或 Mini 的发布包。

本轮层级、归属和展示去向说明见：[DATA_MODULE_HIERARCHY_PLACEMENT_REVIEW_20260813.md](DATA_MODULE_HIERARCHY_PLACEMENT_REVIEW_20260813.md)。

## Fixed Candidate

| 项目 | 固定值 |
|---|---|
| Worktree | `D:\FitnessLedger\work\fitness-ledger-formal-mirror-20260813` |
| Branch | `codex/fitness-ledger-formal-mirror-20260813` |
| Mirror base | `ee19f309bc977e314af878f35795d524bd19b42f` — Self-Service Candidate evidence commit |
| Implementation commit | `06be3e861b77f076c53e643782ea330977e6f97a` |
| Evidence commit | 本文档所在提交 |
| local main | `a63f8a6c3e63e1695898a429ac28a21108957737` |
| origin/main | `d1759117553a8d28437a16c6d456cf6121ba744c` |
| Final status | 应为 clean；未 merge、未 push、未 tag |

## One-command Preview

在 Windows 命令提示符中执行：

```text
D:\FitnessLedger\work\fitness-ledger-formal-mirror-20260813\projects\fitness-ledger\tools\run_data_module_formal_mirror.cmd
```

打开：`http://127.0.0.1:8768/`

启动器只绑定 localhost，默认使用本机的匿名持久化沙盒。关闭方式：回到启动器窗口按 `Ctrl+C`。它不是服务，不会注册开机启动；沙盒只保存候选演示数据，不读取正式 tracker。需要另一个隔离目录时可以显式传入 `--sandbox`，人工体验不需要手动设置环境变量。

## What is included

- 现有一级导航保持不变；没有新增 Data Module 一级导航。
- Daily Entry 中输入未知数值后，出现“建立新的记录项”。普通创建只显示名称、类别、单位、别名和展示位置；稳定 ID、版本和能力放在“高级设置”。
- 创建成功后自动继续当前原始输入，不要求重新输入，再经过 Preview → Confirm → Save。
- Body 页面出现紧凑的“自定义记录项”区块；Tools 页面出现 Data Modules 管理入口。
- 管理中可新建/停用/重新启用类别和记录项，编辑别名、单位、类别、展示位置，并打开历史。
- 新模块默认不开放 Analysis、Cloud、Mini；Cloud dry-run 只生成本地结果，不发网络请求。
- 停用只阻止新记录，已有历史继续可见；记录保存保留 definition snapshot 和版本信息。

## Machine evidence

最终 Implementation commit 上已执行：

| 检查 | 结果 |
|---|---|
| Formal Mirror Microsoft Edge browser E2E | PASS |
| Engine tests | 6/6 PASS |
| Self-Service process/restart test | PASS |
| Static test | PASS |
| Web candidate test | PASS |
| Mini contract test | PASS |
| Python compileall | PASS |
| JavaScript syntax checks | PASS |
| `git diff --check` | PASS |
| Candidate project status test | PASS |
| Cloud sync status test | PASS |

Formal Mirror Browser E2E 覆盖：

1. Daily Entry 未知数值现场创建第一个 Numeric Module；
2. Preview 零写入，Confirm 后出现正式 Module Record；
3. History 和 Normal Export 可见；
4. Tools 管理入口创建第二个模块；
5. 新类别并创建两个模块；
6. 类别停用/重新启用；
7. 别名冲突显示普通用户错误，不显示 JSON code；
8. 编辑名称/别名/Placement，stable module_id 保持不变；
9. 停用后历史保留、新记录被阻止、重新启用；
10. 结束进程后用同一匿名沙盒重启，定义和历史仍在；
11. Analysis 协议边界未改变；
12. Cloud dry-run `network_request_made=false`；
13. Desktop / narrow viewport 路由和横向溢出检查；
14. Body 页面扩展区幂等，不重复插入。

## Safety snapshot

本次最终状态读取到的正式环境事实：

- 正式 tracker 当前 SHA256：`D5ED2C675613A9809F9DA923A90861C54E74AF07C5434C824A9BBA21FC772D2B`
- 正式 movement dictionary 当前 SHA256：`0A5DA6343E7C145B0241CFF829B5F625FE033E99EE0BEF724C1FEDB290A587EA`
- 正式 deployment：`CURRENT`，333 个文件比较无 missing/different；
- Cloud：`SYNCED`，cloud verified；
- Formal Mirror：明确传入临时 tracker、dictionary、backup 和 definition store；
- Cloud：本次浏览器 E2E dry-run 网络请求为 `false`；
- Mini：零发布；remote：零 push；正式 tracker：零写入。

正式 tracker 与 dictionary 的上述 SHA 是最终检查时的当前事实。它们与更早历史快照不同，但这次 Mirror 没有访问或写入正式数据目录，不能把差异归因于本候选。

## Minimal Human Review Script

### A — 从 Daily Entry 创建第一个模块

1. 打开 Daily Entry。
2. 输入：`今天晨间脉搏 58`。
3. 点击 `Parse & Review`。
4. 在创建表单中确认名称，填写单位 `bpm`，保持 Body 和页面摘要。
5. 点击 `创建并继续`，确认页面直接进入当前记录 Preview，没有要求重新输入。
6. 点击 `确认并保存`，再打开 Body 和“查看历史”。

### B — 从 Tools 管理第二个模块

1. 打开 Tools → `Manage Data Modules`。
2. 新建一个普通数值项，例如“日间体温”，单位 `C`。
3. 回到 Daily Entry 输入该别名和数值，检查仍然走同一套 Preview → Confirm → History。

### C — 类别与泛化

1. 在 Tools 中新建一个简单类别，例如“恢复状态”。
2. 在该类别下建立两个不同数值项。
3. 检查管理页按类别分组，Body 扩展区不会生成一页一项或无限卡片。

### D — Schema Evolution

1. 编辑一个模块的名称、别名或展示位置，确认高级信息中的稳定标识不变。
2. 停用它，确认历史仍然可见，新记录被阻止。
3. 重新启用，确认可以继续记录。

### E — Downstream capability

在 Data Modules 管理页查看 `配套能力`：Normal Export 已接入；Analysis、Cloud dry-run、Mini renderer 默认关闭/仅候选检查。高级设置可以打开 Analysis，但本轮只判断契约提示和安全状态，不进行发布或联网。

## What I am reviewing

1. 新增数据模块的行为是否符合预期；
2. Registry-driven 泛化是否自然，没有为某一个业务名词增加专用页面；
3. Parse → Preview → Save → History 是否顺畅且不重复输入；
4. 新模块加入后，Body、Normal Export、Analysis gate、Cloud dry-run、Mini contract 的配套状态是否符合预期；
5. 当前 Candidate 是否值得进入正式 UI、New Category、Placement 阶段。

## Explicitly not yet production

本包仍未进行：

- main merge；
- remote push；
- production deployment；
- formal tracker migration；
- CloudBase upload；
- Mini Program publish；
- AnalysisExportRequest public protocol change。

人工 Review 完成前，不应把本镜像 URL 当作线上入口，也不应把匿名沙盒数据当作正式个人数据。
