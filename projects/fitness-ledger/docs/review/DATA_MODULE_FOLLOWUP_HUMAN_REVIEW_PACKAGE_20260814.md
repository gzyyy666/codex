# Fitness Ledger Data Module Follow-up Human Review Package

本轮是在既有 Data Module Candidate 上的受控 follow-up，不扩大到 New Category、正式 Placement、生产 Cloud/Mini 或公共 `AnalysisExportRequest` 协议变更。

## Fixed Candidate

- Worktree: `D:\FitnessLedger\work\fitness-ledger-data-module-followup-20260814`
- Branch: `codex/fitness-ledger-data-module-followup-20260814`
- Base: `5a874088bd87d013a7f435840323532331225c95`
- Implementation commit: `ac5d1fe13de22f88f652fc6a70cf0839d438cdac`
- Evidence commit: 本文档所在 commit，随后生成
- Review URL: `http://127.0.0.1:8768/`
- Anonymous sandbox: `C:\Users\26087\AppData\Local\FitnessLedger\formal-mirror-followup-review-20260814`
- Stop: 关闭该临时 Python review 进程；它不是开机服务，也不写正式 tracker

## 本轮新增

1. Daily Entry 中增加一个不占主视线的“给 LLM 的录入模板”按钮。
   - 按钮每次打开都从当前 Registry 即时生成。
   - 只含启用记录项的名称、别名、类别、单位、等级和校验规则。
   - 不含个人历史、原始输入或私有备注。
   - 支持复制和下载 JSON；新建模块后重新打开会自动出现。

2. 每个数值模块增加可选的“允许统计趋势”能力。
   - 默认关闭；打开后管理卡片出现“看趋势”。
   - 统计只读本地 Data Module History，显示最新值、平均值、变化和简洁趋势线。
   - 当前只支持每日一个数值；不会改变普通录入、History 或 Normal Export。

3. 增加候选级 Cloud / Mini 就绪检查。
   - 检查允许进入 Cloud dry-run 的模块是否完整进入候选 payload。
   - 检查允许小程序读取的模块是否可由现有通用 Mini contract 渲染。
   - 明确显示“无网络、无需新增页面、公共 Analysis 协议未改变”。

## 人工体验路径

### A. LLM 模板

1. 打开 `http://127.0.0.1:8768/`。
2. 进入 `Daily Entry`。
3. 点击输入区下方的小字按钮“给 LLM 的录入模板”。
4. 判断模板是否清楚、是否只包含当前可用模块；可点击“复制模板”或“下载 JSON”。

### B. 新模块自动进入模板

1. 进入 `Tools → 编辑数据模块`。
2. 新建或编辑一个每日数值，例如 `腰围`、`每日肌酸`或`睡眠评分`。
3. 返回 `Daily Entry` 再打开模板。
4. 确认新模块已经出现，且仍然必须经过 `Preview → Confirm` 才能保存。

### C. 可选统计

1. 在数据模块编辑页打开“允许统计趋势”。
2. 按正常流程录入同一模块的两条或多条不同日期记录。
3. 在模块卡片点击“看趋势”。
4. 判断趋势线、最新值、平均值和变化是否足够直观；关闭能力时不应显示统计入口。

### D. Cloud / Mini 就绪检查

1. 在数据模块管理页找到“配套识别 / 安全默认”。
2. 点击“检查候选就绪状态”。
3. 确认 Cloud dry-run、Mini contract 均显示就绪，且没有网络、上传或发布动作。

## Final verification

- `tools/data_module_engine_test.py`: PASS，8 tests
- `tools/data_module_static_test.py`: PASS
- `tools/data_module_web_candidate_test.py`: PASS
- `tools/data_module_mini_contract_test.js`: PASS
- `tools/data_module_formal_mirror_browser_e2e_test.py`: PASS
- Browser evidence includes: template open, template registry auto-update, optional trend view, release readiness panel, preview zero-write, confirm/history, delete, retire/history/re-enable, stable ID, restart persistence, desktop/mobile width checks
- Python syntax: PASS
- JavaScript syntax: PASS
- `git diff --check`: PASS

## Explicitly not production

- 未 merge main
- 未 push remote
- 未修改 `D:\FitnessLedger\app`
- 未修改正式 tracker 或 movement dictionary
- 未上传 CloudBase
- 未发布小程序
- 未修改公共 `AnalysisExportRequest` 协议
