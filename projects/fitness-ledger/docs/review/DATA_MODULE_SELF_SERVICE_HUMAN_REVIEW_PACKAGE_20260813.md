# Fitness Ledger Self-Service Data Module Human Review Package

这是当前 Self-Service Candidate 的固定人工 Review 对象。范围到此停止：普通用户可以在隔离 Candidate 页面创建 Category/Module、保存定义并完整体验记录链路；本包不授权正式产品接入。

## Fixed Candidate

- Worktree：`D:\FitnessLedger\work\fitness-ledger-data-module-candidate-20260812`
- Branch：`codex/fitness-ledger-data-module-candidate-20260812`
- Base：`a63f8a6c3e63e1695898a429ac28a21108957737`
- Engine Candidate Commit：`b77766969d0caf7383c277a5f4ddd8dd0762bc6b`
- Previous Evidence Commit：`05be3c3481e9dca1a3806fd06f411bd13e3e644c`
- Previous metadata commit：`d13bdbf57e151b9eddb4e9d7abe981b25cc3b535`
- Self-Service Implementation Commit：`186b828`（`Data Module Self-Service Candidate`）
- Evidence Commit：本文件所在的最终 evidence commit；完成提交后以 `git rev-parse HEAD` 记录完整 SHA。
- 最终 Git Status：evidence 提交后必须 clean。

## Safety

- 正式 tracker `D:\FitnessLedger\app\data\tracker.json` SHA-256：`40237d008351a506886e652d541cfc6ca13b65914ae7ae9cb3fc2a78cb2369ae`
- 正式 movement dictionary SHA-256：`6abf5c9a4bb4559a2fa14bd93b3e366a7e339a8fbfab7039746fcd57e269c058`
- 正式 deployment：`CURRENT`，333 个文件无 missing/different。
- Cloud：既有状态 `SYNCED`；本 Candidate 只做本地 dry-run/hash/verify/roundtrip，`network_request_made=false`，无 mutation。
- Mini：只检查本地 renderer contract，零发布。
- Remote：零 push、零 merge、零 tag、零 PR。
- `D:\FitnessLedger\app`：零写回；正式 8766 服务未启动。
- 电源：未修改 Windows sleep/hibernate；没有需要后台保持运行的测试任务。

## Automated Acceptance

| Area | Result | Evidence |
|---|---|---|
| Engine unit | PASS | `python tools/data_module_engine_test.py`：6 tests |
| Self-service integration | PASS | `python tools/data_module_self_service_test.py` |
| Persistence / atomic write | PASS | Candidate definition store、checkpoint、simulated write failure rollback |
| Process A/B restart | PASS | 两个独立 Python 进程；定义、rename、placement、history、alias 均恢复 |
| Negative validation | PASS | duplicate ID/alias、bad unit/range/behavior/renderer/coordinate、retired category、immutable ID |
| Browser/UI E2E | PASS | `python tools/data_module_browser_e2e_test.py`，Microsoft Edge headless 真实页面操作 |
| Web HTTP contract | PASS | `python tools/data_module_web_candidate_test.py` |
| Static genericity | PASS | `python tools/data_module_static_test.py`；无 module-specific business branch |
| Mini contract | PASS | `node tools/data_module_mini_contract_test.js` |
| Syntax | PASS | Python compileall、JavaScript syntax/test |
| Diff hygiene | PASS | `git diff --check` |
| Candidate regression | 0 | 既有 Candidate engine/static/web/Mini 测试无新增失败；历史无关失败未被强行改绿 |

Browser E2E 实际覆盖：新 Category、新 Numeric/Quantity Module、自动 stable `module_id`、alias recognition、Preview zero write、Confirm/History、编辑 label/alias、semantic slot/order Placement、Module retire/re-enable、Category retire 后禁止新增、downstream、Data Check。

## Genericity Proof

- Module ID 由定义身份稳定生成，不由业务名称分支硬编码。
- Parser 只扫描运行时 Registry 的 label/alias；测试中的 Category、Module label、alias 使用随机 token，且从未写入源码或静态 fixture。
- 第二个运行时 Module 复用同一套 Parse → Preview → Save → Query/History/Export 流程。
- 自定义 Category 进入运行时 Category Registry；Body/Diet/Training/Movement 的既有 Core 分支未被改写。
- capability 默认安全：record/query/history/export 开启；analysis/cloud/mini 默认关闭，并由各自 gate 控制。

## Review Launcher

最简单入口，在 Candidate Worktree 根目录执行：

```powershell
python projects\fitness-ledger\tools\run_data_module_candidate_preview.py --open
```

打开：`http://127.0.0.1:8767/data-module-candidate.html`

当前 8767 Candidate listener 已启动，页面返回 HTTP 200 且为 Self-Service 版本。正常前台启动时按 `Ctrl+C` 关闭；当前隐藏启动的临时进程可用以下精确端口命令关闭：

```powershell
$candidateListener = Get-NetTCPConnection -LocalPort 8767 -State Listen
Stop-Process -Id $candidateListener.OwningProcess
```

它使用匿名临时 tracker、movement dictionary、definition store；进程结束后临时文件自动删除。不会读取或写入 `D:\FitnessLedger\app`。

## Human Review Script

### A — 自助创建第一个 Numeric Module

1. 在 Category 管理中输入名称，例如 `Recovery`，ID 可留空；点“预览创建 Category（零写入）”，确认 `write_attempted=false`。
2. 确认创建 Category。
3. 创建 Module，例如 `腰围测试`，Category 选择刚创建的 Category，Data type 选 Quantity，单位 `cm`，填一个 alias 和合理范围。
4. 预览并确认保存；判断页面自动出现稳定 Module ID、alias、renderer、slot/order 和安全 capability 默认值。

### B — Record / History

1. 在 Natural-language Record 输入 `今天 <alias> 82.5 cm`。
2. 点击预览，确认没有写入；再确认保存。
3. 点击 History，确认出现稳定 `record_id`、日期、数值、单位、definition version。
4. 刷新页面，确认 Definition 和 History 仍然存在。

### C — 第二 Module 泛化

在同一 Category 再创建 `静息心率测试`，单位 `bpm`，换一个 alias。用同一 Record 区域完成 Preview → Confirm → History；判断没有新增专属页面或业务分支。

### D — Schema / Lifecycle / Placement

编辑 Module 的 label、alias、Category、renderer、section、slot、order；确认 stable Module ID 不变、version 增加、history 保留。停用后确认历史仍可见、新记录受阻；重新启用后恢复。实际单位变化若没有显式迁移应被拒绝。

编辑/停用/重新启用 Category；停用 Category 时确认不能创建新 Module 或新记录。

### E — Downstream

点击 downstream 刷新，检查 Normal Export、Analysis gate、Cloud dry-run、Mini renderer contract、Presentation。重点判断新增 Module 是否自动出现于对应能力，同时 Cloud 仍显示无网络请求、raw/private 未泄漏、没有 AnalysisExportRequest v1.1 公共协议变化。

## What I am Reviewing

1. 新增 Category/Module 是否真的无需改代码、fixture 或 registry。
2. Registry-driven 泛化是否自然。
3. Parse → Preview → Save → History 是否顺畅、可追踪、可恢复。
4. semantic Category/Section/Slot/Order/Renderer/Visible Placement 是否足够清楚且没有坐标式布局耦合。
5. Export、Analysis、Cloud dry-run、Mini contract 是否随 Module capability 正确跟随。
6. 当前 Candidate 是否值得进入下一阶段：正式 UI、New Category、正式 Placement 和生产接入。

## Explicitly Not Yet Production

仍未进行：

- main merge；
- push / tag / PR；
- production deployment；
- formal tracker 或 formal registry migration；
- CloudBase upload 或 real Cloud mutation；
- Mini Program publish；
- AnalysisExportRequest public protocol change；
- 真实历史数据单位迁移；
- 旧 paused Custom Daily Metric experiment 的恢复。

下一步是人工 Candidate Review。Review 未通过前不继续扩大 Data Module 功能范围，也不进入正式 UI、New Category、Placement 或生产 Cloud/Mini 阶段。
