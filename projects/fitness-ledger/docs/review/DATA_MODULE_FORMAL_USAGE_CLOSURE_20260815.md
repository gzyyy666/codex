# Fitness Ledger Data Module 正式使用体验收口报告

日期：2026-08-15  
状态：Candidate，可直接人工 Review；尚未进入正式部署。

本报告是 2026-08-14 完整实现报告之后的最终体验修正，以下结论覆盖旧报告中关于 Diet 空页、Training 空页、Movement 归类和返回入口的旧描述。

## 1. 本轮结果

Data Module 现在按正式使用者理解工作：新增记录先归入 Body、Diet、Training 或“其他扩展”，再沿用所选类别原有的记录卡、详情、搜索、历史和导出流程。

- Body：有同日原生 Body 记录时，新增数值加入原卡片；只有新增数值时，仍生成原生 Body slip。
- Diet：有同日饮食记录时，新增数值和 P / C / F 使用同一信息区；只有新增数值时，仍生成原生 Diet slip，不再显示空页。
- Training：有同日训练时，新增数值进入训练 facts；只有新增数值时，仍生成原生 Training session card，不再依赖已有训练记录。
- Movement：已从“所属类别”选择中移除。动作页不是每日标量记录的自然归属；“其他扩展”记录仍可选择在 Movement 页角落显示小模块。
- 页面摘要行：不再提供，也不会生成独立摘要。
- 详情：新增记录进入身体、饮食或训练的原有分组；没有内容的分组自动隐藏，包含新增记录的分组提前。

## 2. 新建和编辑体验

新建弹窗只保留实际需要的字段：

1. 名称、单位和常用说法；
2. 所属类别；
3. 显示方式与位置；
4. 折叠的统计、分析、Cloud 和小程序能力。

Movement 不再出现在所属类别中。无单位数值仍可保存。编辑弹窗打开时，页面宠物和鼠标奖杯会隐藏，不再遮挡字段；Data Module 管理页同样保持无宠物遮挡的专注状态。

## 3. 页面与层级

- Tools 首页和左侧导航均保留 Data Module 入口。
- Data Module 管理页去掉流程宣传卡和冗长类别说明，类别直接显示为 Body / Diet / Training / 其他扩展。
- Body、Diet、Training、Movement 和 Dictionary 的大标题下不再保留重复说明式副标题；Daily Entry 保持正式桌面版构图。
- 所有一级页面使用固定在左下角的返回 Home。
- Tools 子页固定返回 Tools。
- Dictionary 固定返回上一层。
- 原页面已有的重复返回按钮会隐藏。
- 长详情弹窗的关闭按钮保持 sticky，页面滚动后仍可退出。

## 4. 完整功能链路

已经实际运行并验证：

```text
定义记录项
→ 别名识别
→ 自然语言 Preview（零写入）
→ Confirm Save
→ History / Query
→ Body、Diet、Training 原生页面展示
→ 打开当天详情
→ JSON / 常规导出
→ Analysis gate / Statistics
→ Cloud dry-run
→ Mini contract
```

停用后历史保留、新写入受阻；重新启用后可以继续记录。删除记录项和自定义类别也在隔离沙盒中通过。

## 5. 最终截图

截图来自当前 `127.0.0.1:8768` 候选服务和匿名沙盒。

### Diet：无原生饮食数据时，腰围仍使用 Diet 原生日卡

![Diet 原生记录卡](C:/Users/26087/.codex/visualizations/2026/08/15/fitness-ledger-data-module-followup-20260814/audit-final/03-diet.png)

### Data Module 管理页：类别收敛，Movement 不再作为归属类别

![Data Module 管理页](C:/Users/26087/.codex/visualizations/2026/08/15/fitness-ledger-data-module-followup-20260814/audit-final/06-tools-modules.png)

### 新建弹窗：字段直接、无重复引导、无宠物遮挡

![新建记录项弹窗](C:/Users/26087/.codex/visualizations/2026/08/15/fitness-ledger-data-module-followup-20260814/audit-final/07-module-form.png)

### 当天详情：腰围直接进入饮食记录，空分组被隐藏

![Diet 记录详情](C:/Users/26087/.codex/visualizations/2026/08/15/fitness-ledger-data-module-followup-20260814/audit-final/08-diet-record-detail.png)

其他逐页截图保存在：

```text
C:\Users\26087\.codex\visualizations\2026\08\15\fitness-ledger-data-module-followup-20260814\audit-final
```

## 6. 测试结果

| 测试 | 结果 |
|---|---|
| `tools/data_module_engine_test.py` | PASS，9 tests |
| `tools/data_module_static_test.py` | PASS |
| `tools/data_module_web_candidate_test.py` | PASS |
| `tools/data_module_self_service_test.py` | PASS，含进程重启持久化 |
| `tools/data_module_browser_e2e_test.py` | PASS |
| `tools/data_module_formal_mirror_browser_e2e_test.py` | PASS |
| `tools/data_module_cloud_extension_test.py` | PASS，网络请求 0 |
| `tools/data_module_mini_contract_test.js` | PASS |
| `tools/mini_program_test.py` | PASS |
| Web / Mini JavaScript syntax | PASS，44 files |
| Python syntax | PASS |
| `git diff --check` | PASS |

Formal Mirror 浏览器测试新增明确断言：

- Body / Diet / Training 三类“只有模块记录、没有原生当天记录”都能显示；
- Diet 搜索可检索模块记录；
- 模块日卡可打开当天详情；
- Movement 不再是所属类别；
- 页面小模块仍可选择显示在 Movement；
- 模块表单和详情无宠物遮挡；
- 11 个页面/子页的返回层级正确；
- 桌面和窄屏无水平溢出。

两项既有测试断言漂移一并修正：默认能力新增 `statistics_visible: false`；停用模块仍可识别但应返回 `MODULE_NOT_RECORDABLE`。两项均是测试与现有业务语义对齐，不是放宽断言。

## 7. 安全边界

- Worktree：`D:\FitnessLedger\work\fitness-ledger-data-module-followup-20260814`
- Branch：`codex/fitness-ledger-data-module-followup-20260814`
- 本轮起点：`e20b77e77aecef0949648ad6ea1455eb3d61c8af`
- 正式 tracker：未修改。
- movement dictionary：未修改。
- `D:\FitnessLedger\app`：未回写。
- Cloud：只运行 dry-run，零上传。
- Mini：只验证契约和本地代码，零发布。
- Remote：零 push。
- local main：未修改。

## 8. 人工 Review 入口

统一入口：`http://127.0.0.1:8768/`

建议直接检查：

1. `#diet`：当前腰围已归入 Diet，可看到三个模块日卡；
2. `#body`：静息心率和 Body 原有信息使用同一行样式；
3. `#tools?panel=data-modules`：检查类别、编辑弹窗、位置和下游能力；
4. `#quick`：检查自然语言识别和给 LLM 的录入模板；
5. 修改腰围归属为 Training 后进入 `#training`：即使没有原生训练日，也会出现 Training 原生样式记录卡。

当前应由人工判断：三类原生承载是否符合直觉、编辑是否足够直接，以及 Candidate 是否值得进入正式 UI 和生产接入阶段。
