# Fitness Ledger Data Module 层级与归位 Review

这是在 `DATA_MODULE_FORMAL_MIRROR_REVIEW_PACKAGE_20260813.md` 之后的候选级改动，专门解决“新建选项不清楚、类别和展示位置混在一起”的问题。它仍然只运行在 Formal Mirror Candidate Worktree 和匿名沙盒中。

## 先定下来的数据层级

当前候选只支持一个最小、清晰的记录等级：

1. **记录等级：每日一个数值**
   - 每天最多保存一个值；例如 `腰围 82.5 cm`、`每日肌酸 5 g`、`静息心率 58 bpm`。
   - 这不是页面，也不是分类；它决定的是记录方式。

2. **归属类别：它是什么**
   - `Body`：身体和身体状态，例如腰围、体重、静息心率。
   - `Diet`：饮食和摄入，例如肌酸、饮水、钠。
   - `Training`：训练和有氧相关数值。
   - `Movement`：动作相关数值。
   - `其他扩展` 或自定义分类：没有现成业务页面归属的内容。

3. **展示去向：它出现在哪里**
   - `跟随所属类别页面`：沿用已有页面，不创建新页面。
   - `首页角落小模块`：适合没有专属页面的扩展数据。
   - `只在记录、历史和导出中保留`：可记录、查询和导出，但不占页面位置。
   - `只记录，不自动展示`：完全不自动放入页面。

4. **页面内位置：它在该页面怎样出现**
   - 摘要行；
   - 主内容；
   - 页面角落小模块；
   - 只在历史与导出。

这四层被刻意拆开：**类别决定归属，展示去向决定页面，页面内位置决定布局**。因此不会再因为增加一个数据就生成一个新一级页面。

## 三个实际例子

### 例 1：新增腰围

`今天腰围 82.5 cm`

识别后流程是：

`每日一个数值 → Body → 跟随 Body 页面 → 摘要行/额外指标行 → Preview → Confirm → History`

结果：腰围和 Body 中已有的体重、排便、训练、有氧处于同一份 Body 日记录中；页面只增加一个扩展指标卡/行，不增加“腰围页面”。

### 例 2：新增每日肌酸

`今天每日肌酸 5 g`

识别会建议：

`每日一个数值 → Diet → 跟随 Diet 页面 → 类别页面角落小模块`

结果：肌酸在 Diet 页面作为自定义饮食指标显示，与 `P / C / F` 并列，但不改变原有蛋白质、碳水和脂肪的定义。它仍然沿用同一个输入、历史和导出流程。

### 例 3：没有现成页面的恢复评分

`今天恢复评分 8`

识别会建议：

`每日一个数值 → 其他扩展 → 首页角落小模块`

结果：不创建“恢复评分页面”，只在首页增加一个小模块；如果不想在页面看到它，可以改为“只在记录、历史和导出中保留”。

## 导入、导出、Cloud、Mini 的一致规则

- **导入识别**：新增 `/api/data-modules/import-preview`。它识别正常导出包、Cloud dry-run 包和 Mini contract，列出已知模块、未知模块和孤立记录；只预览，不自动写入。
- **正常导出**：每个模块携带 `record_level` 和 `display_surface`，记录继续携带 definition snapshot 和版本信息。
- **Cloud dry-run**：只包含允许 Cloud 的模块；携带等级和显示去向；原始文本、私有字段和 source hash 继续排除；网络请求仍为 `false`。
- **Mini contract**：继续只支持 `single_metric` / `metric_history` 两种紧凑 renderer；模块额外携带等级和显示去向；`page_required` 仍为 `false`，不会为新数据自动创建小程序新页面。
- **Analysis**：没有修改 AnalysisExportRequest 公共协议；分析可见性仍然是高级能力，默认关闭。

## 人工 Review 重点

1. 在 Daily Entry 输入 `今天晨间脉搏 58`，看是否能先看懂“等级、类别、显示去向”。
2. 用 `腰围` 判断 Body 额外指标行是否自然。
3. 用 `每日肌酸` 判断 Diet 中 P / C / F 旁边的扩展指标是否自然。
4. 用 `恢复评分` 判断“首页小模块、不新增页面”是否足够清楚。
5. 打开 Tools → 数据模块，确认卡片上能直接读出：归属、显示和页面内位置。
6. 确认导入识别只预览、不写入；Cloud/Mini 只按允许项继续，不发生发布或联网。

## 本轮边界

- 不创建新的一级页面；
- 不把正式 Body/Diet/Training 结构改造成新 schema；
- 不写 `D:\FitnessLedger\app`；
- 不 merge、push、tag；
- 不进行 CloudBase 上传、Mini 发布或正式 tracker 迁移；
- 不修改 AnalysisExportRequest 公共协议。

机器截图保存在临时目录：

- `C:\Users\26087\AppData\Local\Temp\fitness-ledger-formal-mirror-create-form.png`
- `C:\Users\26087\AppData\Local\Temp\fitness-ledger-formal-mirror-review.png`

两张截图均由本机 Microsoft Edge headless 临时会话捕获并检查过。
