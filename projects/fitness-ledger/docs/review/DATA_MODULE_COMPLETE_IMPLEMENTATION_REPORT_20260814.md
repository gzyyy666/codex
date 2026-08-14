# Fitness Ledger Data Module 完整实现与界面复查报告

日期：2026-08-14
范围：Data Module Candidate 隔离候选工作树、桌面 Web 候选预览、Cloud dry-run、Mini 契约检查。
正式业务目录、正式 tracker、线上 Cloud 和线上 Mini 均未修改。

## 1. 本次收尾前仍未完成的问题

上一轮候选已经具备 Data Module 的底层能力，但人工体验仍有以下缺口：

- “页面摘要行”仍然出现在位置选择中，旧定义会被错误地当成独立展示方式。
- 选择类别页位置后，页面实际展示没有稳定跟随选择。
- 同类数据旁边仍可能出现重复的独立胶囊或扩展记录大框。
- 页面角落小模块带有外层说明框，位置不够靠边，也不够固定。
- Tools 首页多出一个大型数据模块卡，造成空白和视觉重心混乱。
- Daily Entry 的活动页面仍使用中文大标题和冗长说明，旧路径中还存在问号占位文本。
- 无单位数据、类别删除、记录项删除和编辑归位需要做最后一次真实验证。

## 2. 已完成的实现

### 2.1 位置语义已经收敛

现在用户可选择的类别页位置只有：

| 选择 | 实际效果 |
|---|---|
| 主内容 | 直接加入该类别原有记录行，复用 Body / Diet / Training 的原有排版。 |
| 详情区 | 列表页不增加一行，打开某条记录后出现在已有详情记录中。 |
| 仅历史 | 不占页面位置，但保留查询、历史和导出。 |
| 仅记录，不展示 | 保存、历史和导出保留，不自动进入页面。 |

“摘要行”不再是新建选项。旧定义中的 `summary` 仍可读取，但会自动归一为 `main/top`，因此不会丢历史，也不会继续生成旧摘要行。

### 2.2 现有页面中的呈现

- Body：扩展数据直接成为原有 Body 记录卡中的指标行。
- Diet：扩展数据可以和 P / C / F 在同一宏量行中并列，不改变原宏量字段含义。
- Training：扩展数据复用训练记录事实区；没有合适位置时可以只显示在固定角落或详情。
- Detail：详情区数据插入现有结构化详情，而不是另造一个“扩展记录”大面板。
- Page Widget：只保留数据胶囊本身；去掉“页面小模块”外层框和标题。

### 2.3 自助录入和识别

当前候选仍限定为“每日一个数值”，例如：

```text
2026-08-13 腰围 82.5 cm
2026-08-13 静息心率 58 bpm
2026-08-13 睡眠评分 7
```

流程为：

```text
Daily Entry → 输入自然语言 → Preview → 确认 → 保存 → 查询 / 历史 / 导出
```

新数据首次未识别时，只进入同一套编辑流程：确认名称、所属类别、显示方式。无单位可以保存，系统会按数字记录处理。

### 2.4 编辑、删除和演化

- 记录项支持编辑名称、别名、单位、类别、显示方式和下游能力。
- 自定义类别支持停用、重新启用和删除。
- 记录项支持停用、重新启用和删除。
- 系统类别不能删除。
- 仍有记录项的自定义类别不能直接删除，必须先处理所属记录项。
- 修改名称或类别不会改变稳定 `module_id`；停用后历史仍可见，但不能新增记录。

本次在匿名候选沙盒中实际验证了：腰围 `主内容 → 详情区 → 主内容` 的编辑变化、临时分类创建与删除、无单位睡眠评分的创建和保存。

### 2.5 Tools 和 Daily Entry

- Tools 侧栏保留“编辑数据模块”入口。
- Tools Overview 不再插入第三个大型数据模块卡，恢复原有工具区的秩序。
- Daily Entry 活动标题恢复为英文 `Daily Entry`。
- Daily Entry 保留必要的中文输入提示，但删除无效的撤销按钮和冗长宣传式说明。
- Body / Diet / Training 的大标题下不再显示重复的营销式副标题。
- 活动 Daily Entry 路径不再显示 `???` 或 `????` 占位文本。

## 3. 截图证据

截图均来自 `127.0.0.1:8768` 候选服务，使用匿名持久化沙盒，不读取正式 tracker。

### 3.1 Tools：去掉额外大卡片，保留侧栏入口

修改前，Data Module 被作为第三张大卡插入 Tools 首页，卡片内部留下大片空白，造成“中间莫名其妙空一块”的问题。

![修改前：Tools 首页额外的大型数据模块卡和空白区域](C:/Users/26087/.codex/visualizations/2026/08/14/fitness-ledger-data-module-complete-review-20260814/before/01-tools-before.png)

修改后，Overview 恢复原来的 Export / Archive Health / Movement Dictionary 结构，Data Module 只从左侧 Reference 导航进入。

![修改后：Tools 首页恢复原有结构，左侧保留编辑数据模块入口](C:/Users/26087/.codex/visualizations/2026/08/14/fitness-ledger-data-module-complete-review-20260814/after/01-tools-after.png)

### 3.2 Body：扩展数据和同类数据并列

修改前的 Body 页面没有可见的候选扩展记录，无法判断它是否真的进入原页面。

![修改前：Body 页面没有候选扩展记录](C:/Users/26087/.codex/visualizations/2026/08/14/fitness-ledger-data-module-complete-review-20260814/before/03-body-before.png)

修改后，静息心率和腰围直接加入 Body 记录卡的原有指标行；它们不再使用独立的大卡片。

![修改后：静息心率和腰围直接进入 Body 原有指标行](C:/Users/26087/.codex/visualizations/2026/08/14/fitness-ledger-data-module-complete-review-20260814/after/03-body-after.png)

### 3.3 页面角落小模块：只保留胶囊

匿名候选中增加了无单位的“睡眠评分 7”作为 Body 页角落小模块。可以看到现在只剩紧凑胶囊，位于右上角，未占用中间内容区。

![修改后：页面角落小模块只显示紧凑胶囊](C:/Users/26087/.codex/visualizations/2026/08/14/fitness-ledger-data-module-complete-review-20260814/after/03-body-widget-after.png)

### 3.4 Data Module 管理页

管理页展示类别、记录项、归属、显示去向、位置、编辑、历史、趋势、停用和删除入口。当前截图中的两个 Body 模块均已归一到“主内容”，页面不再提供“摘要行”选项。

![修改后：Data Module 管理页](C:/Users/26087/.codex/visualizations/2026/08/14/fitness-ledger-data-module-complete-review-20260814/after/02-modules-after.png)

### 3.5 Diet / Training：保留类别原有页面结构

Diet 和 Training 仍使用各自的页面结构，没有因为扩展指标而增加新的大面板；页面标题直接进入记录区，候选数据按所选类别的既有承载方式继续处理。

![修改后：Diet 页面保留原有记录结构并去掉重复副标题](C:/Users/26087/.codex/visualizations/2026/08/14/fitness-ledger-data-module-complete-review-20260814/after/04-diet-after.png)

![修改后：Training 页面保留原有训练档案结构并去掉重复副标题](C:/Users/26087/.codex/visualizations/2026/08/14/fitness-ledger-data-module-complete-review-20260814/after/05-training-after.png)

### 3.6 Daily Entry：恢复英文标题并缩短说明

修改前，活动页面使用“写下今天”等中文大标题，并在多个位置重复解释流程，属于本次反 AI 风格审查中发现的典型“标题 + 空泛说明”问题。

![修改前：Daily Entry 中文大标题和重复说明](C:/Users/26087/.codex/visualizations/2026/08/14/fitness-ledger-data-module-complete-review-20260814/before/06-daily-entry-before.png)

修改后，页面标题为英文 `Daily Entry`，下方只保留实际操作说明；输入框和按钮直接表达“输入 → Review”。

![修改后：Daily Entry 英文标题和直接的输入流程](C:/Users/26087/.codex/visualizations/2026/08/14/fitness-ledger-data-module-complete-review-20260814/after/06-daily-entry-after.png)

### 3.7 本次反 AI 风格审查的结论

截图中重点处理了以下问题：

1. 额外宣传式模块：从 Tools 首页移除。
2. 大标题下的空泛副标题：Body / Diet / Training 删除，Daily Entry 改成事实性短句。
3. 同一条扩展数据重复显示：主内容只留原生指标行，页面小模块只在选择该方式时出现。
4. 页面小模块外层包装过重：改为固定页面锚点上的紧凑胶囊。
5. 入口太多：数据模块只保留 Tools 侧栏入口，未再增加新的一级页面。

截图是视觉证据，不等同于完整的键盘、读屏器和所有断点无障碍审计；本次同时完成了语法、API 和候选场景验证。

## 4. Cloud、Mini、分析和 LLM 配套

### Cloud

新的模块定义和记录可以进入候选 Cloud payload 的三个扩展集合：定义、记录、契约。Cloud dry-run 会校验孤儿记录、稳定 ID、哈希和 raw/private 泄漏；本次没有发生网络上传。

### Mini Program

小程序侧已经有通用的只读 Data Module contract 和 `dataModuleCard` 组件。模块被标记为 `mini_program_visible` 后，Mini 可以按 `module_id / category_id / renderer / latest / history` 读取，不需要为每个新指标新建页面。

本次没有执行 CloudBase 上传或小程序发布。下一次真正接入某个新指标时，只需在 Web 候选中完成定义、确认其 Mini 能力，然后经过 Cloud/Mini 人工验收，最后才由明确的发布任务处理线上配置。

### Analysis / Statistics

- `analysis_visible` 打开后进入候选 Analysis catalog；公共 `AnalysisExportRequest` 协议未改。
- `statistics_visible` 打开后可在 Data Module 管理页查看本地数值趋势、最新值、平均值、变化量。
- 没有打开能力的模块不会被强行送入下游。

### LLM 录入模板

Daily Entry 中的“给 LLM 的录入模板”按钮会按当前启用模块即时生成定义模板。模板不包含个人历史和原始输入；新增模块后重新打开即可看到更新后的名称、别名、单位、类别和记录等级。

## 5. 测试结果

### Candidate 专项

| 检查 | 结果 |
|---|---|
| `tools/data_module_engine_test.py` | PASS，8 tests |
| `tools/data_module_static_test.py` | PASS |
| `tools/data_module_web_candidate_test.py` | PASS；新增断言确认不再提供 summary，旧 summary 自动归一为 main |
| `tools/data_module_mini_contract_test.js` | PASS |
| `tools/data_module_cloud_extension_test.py` | PASS |
| `tools/mini_program_test.py` | PASS |
| `tools/data_module_review_scenarios.py` | PASS；Preview、Save、History、第二模块、演化、Cloud、Mini 全部完成 |
| Python syntax checks | PASS |
| Web / Mini JavaScript syntax checks | PASS |
| `git diff --check` | PASS |

### 已知历史失败

`tools/cloud_payload_test.py` 仍失败在既有断言：

```text
assert '"raw"' not in serialized
```

当前 `fl_data_quality_issues` 中存在合法的质量问题类型值 `target_type: "raw"`，因此该字符串断言会误报。上一轮 base `a63f8a6c3e63e1695898a429ac28a21108957737` 与 Data Module candidate 对照时已经确认这是 `SAME_BASELINE_FAILURE`，不是 Candidate Regression。本次新增 Candidate Regression 数量为 0；未通过复制个人数据、削弱断言或改变业务语义来“修绿”。

## 6. 固定候选与安全状态

### Fixed Candidate

- Worktree：`D:\FitnessLedger\work\fitness-ledger-data-module-followup-20260814`
- Project：`D:\FitnessLedger\work\fitness-ledger-data-module-followup-20260814\projects\fitness-ledger`
- Branch：`codex/fitness-ledger-data-module-followup-20260814`
- Base：`a63f8a6c3e63e1695898a429ac28a21108957737`
- Previous candidate：`35852e647ca7250af52a1f4a01bf832809a6f67e`
- Implementation commit：`91d6df824ceb8fd2f066b10409c7fbf169e4bb22`（`fix: close data module candidate review gaps`）
- Evidence / report commit：本报告所在的独立 evidence commit；最终 hash 在交付时记录。

### Safety

- 正式 tracker SHA：`d5ed2c675613a9809f9da923a90861c54e74af07c5434c824a9bba21fc772d2b`，未变。
- 正式 movement dictionary SHA：`0a5da6343e7c145b0241cff829b5f625fe033e99ee0bef724c1fedb290a587ea`，未变。
- 正式部署：`CURRENT`。
- Cloud 正式状态：`SYNCED`，正式 payload hash 仍为 `1a16c884c1e3f5eb4b9120595618d8820d5ff74e28ccbcc0ff8c5413d42f2af2`。
- Cloud mutation：0。
- Mini publish：0。
- Remote push：0。
- `D:\FitnessLedger\app`：未回写。

## 7. Review 入口

候选监听：`127.0.0.1:8768`。当前运行的是候选工作树，不是正式 Web。

- Data Module 管理：`http://127.0.0.1:8768/#tools?panel=data-modules`
- Tools 首页：`http://127.0.0.1:8768/#tools`
- Body 展示：`http://127.0.0.1:8768/#body`
- Daily Entry：`http://127.0.0.1:8768/#quick`

匿名沙盒：`C:\Users\26087\AppData\Local\FitnessLedger\formal-mirror-followup-review-20260814`。
关闭候选服务：结束监听 `127.0.0.1:8768` 的候选 Python 进程即可；没有注册后台服务。

## 8. 本轮人工 Review 应判断什么

1. 新增一个 Body、Diet 或其他扩展数据时，分类是否直观。
2. 选择“主内容”后，数据是否真的像原有数据一样出现，而不是另起一块。
3. 选择“详情区”后，列表是否保持干净，打开记录后是否能找到它。
4. 页面角落胶囊是否足够小、足够靠边，同时仍然容易发现。
5. Preview → Confirm → Save → History 是否符合正式记录的感觉。
6. LLM 模板、导出、统计、Cloud dry-run 和 Mini contract 是否满足进入下一阶段的条件。

## 9. 明确尚未进行

本报告对应的 Candidate 仍未进行：

- merge 到 local main；
- push 或 tag；
- 正式 tracker migration；
- CloudBase upload；
- Mini Program publish；
- 正式 UI / New Category / Placement 的生产变更；
- `AnalysisExportRequest` 公共协议字段变更。

下一步应是人工 Candidate Review。除非 Review 明确提出新的问题，否则不再继续扩大 Data Module 的工程范围。
