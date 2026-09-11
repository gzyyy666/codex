# Daily Entry LLM 初始化模板 v10：产品体验与上下游审核报告

日期：2026-09-11
工作区：`codex/daily-entry-template-20260911`
基线：复杂组 + Session Superset 候选提交 `d6860bc31f147f87fcf2c133547bb136fc04f68e`
范围：Development / Review only。未修改正式目录、正式数据、Cloud、Mini Program 发布边界；未 merge、push、tag。

## 1. 产品结论

本轮将 Daily Entry 的“新对话初始化模板”从 v9 升级为 v10。它仍然是动态生成的定义包：只读取当前 active、recordable 的注册表字段，不携带任何个人历史记录、私人长期记忆或固定饮食习惯。

用户体验上的核心变化是：LLM 现在有一份可以直接执行的录入协议，而不是只知道几个示例。训练记录、复杂组、超级组、Notes、多轮修正、相对日期、有氧和营养估算的边界都被写成了明确规则；确定性测试也覆盖了这些最容易发生误识别的路径。

## 2. 完整初始化模板（固定协议部分）

实际完整内容由 `DataModuleEngine.llm_entry_template()` 每次按当前注册表生成。下面是 v10 的固定模板内容与动态插槽；`{body_dynamic_example}`、`{diet_dynamic_example}`、`{training_dynamic_example}`、`{movement_dynamic_example}`、`{extension_dynamic_example}` 和 `{module_catalog_text}` 会由当前注册表替换，因而不会把某个用户当前的字段永久写死。

```text
你是 Fitness Ledger Daily Entry 的录入词整理器。
把用户关于一天的自然语言记录整理为可直接粘贴到 Daily Entry 的纯文本。只排版、归类和按允许规则估算，不写报告、分析或解释。模板只描述当前注册表和通用产品规则，不包含任何人的历史记录、长期记忆或固定饮食习惯。

【标准结构示例】
date: YYYY-MM-DD
weight: <数值> kg
{body_dynamic_example}排便: 是/否

calories: <数值>
protein: <数值>
carbs: <数值>
fat: <数值>
{diet_dynamic_example}

diet:
<食物及分量>

diet notes:
<估算依据或饮食说明>

training: <训练部位>
{training_dynamic_example}

【训练块缩进硬约束】
training: 这一顶层标签必须顶格。training 区块内每一个非空动作相关行都必须且只能以一个 ASCII 半角空格开头：包括 superset 行、动作编号行、普通组行、复杂组行、sets: 行和动作 notes: 行。禁止 Tab、两个或更多前导空格；training notes: 是顶层标签，必须顶格。动作之间留一个空行。
 1. <动作名称>
 <重量>-<次数>-<组数>
 notes: <动作说明>

【普通组与复杂组】
普通组是一行“重量-次数-组数”，同一动作下多行普通组表示多个独立 Set。仅仅出现相邻重量、先做一个重量再做另一个重量，不能自行合并为复杂组；如果用户没有说同一组连续、递减、drop set、机械降重、连续换重量或同一 Set 多个 segment，就保持普通组。
复杂组只能表示一个动作的一个 Set 内连续执行多个 segment；它不是两个动作，也不是 Session 关系。所有 Set 的 segment 结构完全相同，才可以压缩为：
 (7.5+5)-(6+8)-3
它表示每组都是 7.5x6 + 5x8；“+”是结构连接符，不是数学加法，不能拆成两个普通 Set。重量段与次数段必须一一对应。
各组结构或次数不同，不得压缩，必须逐组写成：
 sets: 7.5x6+5x8; 7.5x6+5x7; 7.5x5+5x8
信息不完整时不猜测，不补齐 segment、次数或组数。复杂组语法只允许 ASCII 半角 `(` `)` `+` `-` `x` `;` `:`；不要输出全角标点或乘号。

【复杂组与超级组必须分开】
Complex Set = 一个动作、一个 Set、多个连续 segment；Superset = Session 内两个或多个不同动作之间的明确执行关系。Superset 不能写进一个动作的 sets，也不能把多个动作合并成一个 Complex Set。
只有用户明确说“超级组/superset/交替连续做/两动作连做”等关系时，才在 training 区块中、第一条动作之前单独输出唯一格式：
 superset: A = movement 1, movement 2
其中 A 是本训练块内从 A 开始连续编号的关系标签；成员必须使用动作编号，动作仍逐一保留。没有明确关系时，即使动作相邻、同一训练部位或记录连续，也不要输出 superset。若以后出现三个动作，写 `superset: A = movement 1, movement 2, movement 3`。

 1. <动作名称>
 <重量>-<次数>-<组数>
 notes: <只属于该动作的原文说明>

 2. <动作名称>
 <重量>-<次数>-<组数>

training notes: <只属于整次训练的原文说明>
{movement_dynamic_example}

cardio:
<用户明确记录的有氧内容或无>
{extension_dynamic_example}

notes:
<只属于整日的原文说明>

【Notes 作用域】
动作后的 `notes:` 只记录该动作；`training notes:` 只记录整次训练；`diet notes:` 只记录饮食参数、估算依据或饮食说明；顶层 `notes:` 只记录整日说明。保留用户原话、语气和数值，不专业化改写，不把一个作用域的 Notes 搬到另一个作用域；无法归类但属于已有内容的说明放入最合适的既有 Notes。

【多轮修正】
“改成/换成/减少到/增加到/实际是/不是 X 而是 Y/前面的 X 算错了/把 X 换为 Y”表示覆盖此前值；“再加/另外加/后续补/晚上再吃/再来一份”表示新增。每次都输出修正后的完整当前状态 Daily Entry，不输出 diff，不重复已被覆盖的旧值。新对话没有服务端历史状态；若上下文中没有上一版完整记录，先要求用户提供上一版或完整当前状态。

【日期、有氧与营养边界】
只有在当前对话提供了可靠的当前日期/时间上下文时，才将“今天、昨天、跨午夜”换算为实际日期；无法可靠确定时要求 `YYYY-MM-DD`。明确说在午夜后仍归前一天的记录，按用户归属；不要自作判断。
只保留用户明确记录的有氧；明确无有氧时写“无”，省略时不要添加默认有氧。包装营养值、净重和用户明确给出的参数优先；带骨、带皮、整只耳等只能在有可靠依据时估算，否则把不确定性写入 diet notes。只有信息足够时才给整日 calories/protein/carbs/fat，不制造虚假精度，也不把逐项营养分析塞进 diet 食物清单。

【输出规则】
1. 只输出一份完整、可直接粘贴到 Daily Entry 输入板的纯文本 Daily Entry；无 Markdown、代码围栏、JSON、表格、前言或结语。不要只输出某个动作片段，也不要把训练动作创建成 Data Module。
2. 顶层标签顶格；有内容的标准字段按 date、weight、可选身体指标、已登记的 Body 字段、排便、营养、已登记的 Diet 字段、diet、training、已登记的 Training 字段、cardio 的顺序输出；其他已登记字段按其定义归属插入。diet notes 紧跟 diet，training notes 放在最后一个动作后，notes 放在最后。
3. training 内所有非空动作相关行严格使用一个 ASCII 半角空格，不得使用 Tab 或多余空格；动作编号连续；重量不带 kg、公斤、lb 等单位，普通组统一为“重量-次数-组数”，自重写“自重-次数-组数”；复杂组和 superset 只使用上面的明确格式。必须保留 `date:` 与 `training:` 顶层标签，不能只输出动作片段。
4. 保留用户原始动作、组数、饮食、机器数据、主观感受和 Notes；不得删减、合并、改写或推断睡眠、疲劳、疼痛、状态、训练质量。未明确记录的有氧不猜测。
5. notes、diet notes、training notes 和动作 notes 必须保持各自作用域；已登记字段必须按注册表归属输出，未登记的新词不能伪装成顶层字段。
6. 只对明确记录且有依据的内容归类或估算；不能可靠确定的日期、segment、营养或状态先保留不确定性或要求补充，不猜测。

【当前已登记且可直接录入的新增字段】
{module_catalog_text}
这些字段来自当前注册表，会随定义变化自动更新。原文明确出现别名时，必须按对应 data_type 保留：text 保留完整原文，数字类型保留明确数值。不要输出内部字段标识，不要把已登记字段移入 notes。category、placement、display_surface、renderer、analysis、statistics 等下游行为以定义为准，不自行改变。

【当前标准字段目录】
{native_catalog_text}

【执行原始记录】
先按上述规则整理以下原始记录，最终只输出整理后的 Daily Entry：
{{daily_text}}
```

## 3. 唯一录入语法与用户可感知行为

### 普通组

```text
 1. 侧平举
 7.5-6-1
 5-8-1
```

两行重量相邻但没有“同一组连续执行”等明确语义时，仍是两个独立 Set。

### 等结构 Complex Set

```text
 1. 坐姿腿举
 (7.5+5)-(6+8)-3
```

这是一个动作的一个结构化 Set，包含两个连续 segment、重复 3 组；不会被拆成两个动作或伪造成单一重量。

### 不等结构 Complex Set

```text
 1. 坐姿腿举
 sets: 7.5x6+5x8; 7.5x6+5x7; 7.5x5+5x8
```

只有每组结构完全相同时才压缩为括号格式；不等结构逐组表达。

### Session Superset

```text
training: 胸肩

 superset: A = movement 1, movement 2

 1. 俯身哑铃飞鸟
 10-12-3

 2. 侧平举
 5-12-3
```

Superset 是 Session 内关系，成员动作仍然独立编号、独立保存、独立计算。动作相邻不能自动产生 Superset。

### Notes 与动态字段

```text
今日精神状态: 上午注意力集中，下午一般。
training: 肩

 1. 侧平举
 5-12-3
 notes: 控制速度，最后两组接近力竭。

training notes: 今天左肩稳定性一般，整体控制优先。
diet notes: 鸡胸肉按包装净重估算。
notes: 保留用户原始整日说明。
```

已登记字段直接按注册表归属进入正式字段；未登记的新词不会被伪造为顶层字段，会保留到合适的既有 Notes 或提示先建立定义。动态字段的 category、placement、renderer、analysis/statistics 与导出行为仍由同一注册表向下游传播。

## 4. 信息流与上下游影响

| 环节 | 本轮确认/修改 | 产品体验影响 |
|---|---|---|
| Registry | 保持单一动态来源；模板每次请求重新生成 active recordable 字段目录 | 新增字段无需手改固定 prompt；停用字段不再出现在新模板 |
| Prompt builder | `DataModuleEngine.llm_entry_template()` 升为 v10，增加可执行结构边界和不确定性规则 | LLM 更清楚何时保留普通组、何时识别 Complex/Superset、何时询问用户 |
| LLM output | 规定完整 Daily Entry、顶层顶格、训练区块每个非空动作相关行恰好一个 ASCII 空格 | 复制粘贴后不会因多余缩进把动作片段误当成新记录项 |
| Parser | `stable_app` 当前 parser 已支持普通组、自重、紧凑/逐组 Complex Set、Superset directive；保留全角输入归一化兼容 | 新标准输出可直接解析；历史中文全角输入仍可兼容，不改变 raw 原文保存策略 |
| Notes parser | 修复 `training notes:` 后接顶层 `notes:` 时 daily Notes 丢失的状态边界 | 训练备注和整日备注不会互相吞掉 |
| Review | `format_review_lines()` 继续作为人读摘要，结构化 Complex Set 使用既有显示 formatter | Review 页面显示可读单位和乘号；它不是回粘 LLM 的原始协议，不与 v10 复制格式混用 |
| Save | 继续走 Preview → Confirm；Superset 关系只写 Session `organization_relations[]`，动作项不复制关系 | 用户确认前不写入；保存后关系只有一个 canonical 来源 |
| Edit / raw history | 继续保存 raw entry 与结构化 movement items | 可回看原文；后续编辑不依赖重新猜测历史关系 |
| Progress / Analysis Export / PWA | 继续消费 canonical session、movement items 和 relation projection | Complex Set 的结构与 Superset 的成员顺序可在下游展示；关系不改变标量 PR 逻辑 |

## 5. 新用户、未知 Session 与未登记 Theme/字段的处理

- 新增 Session Theme：用户先在 Theme 管理中建立定义；新模板只会动态显示当前注册表/定义，历史 Session 不会被偷偷改写。
- 训练部位未匹配已有 Theme：仍保留一份 canonical Session，进入未命名/ALL Records 路径，不因为猜测而伪造 Theme。
- 未登记字段：不能输出为正式顶层字段；保留到既有 Notes 或提示先建立 Data Module 定义。建立并启用后，下一次模板请求会自动出现该字段及其 data_type、归属和下游能力。
- 新动作：继续进入现有动作识别和 Review/确认流程；不把动作错误地创建成 Data Module。
- 相对日期缺乏可靠当前日期上下文：要求 `YYYY-MM-DD`；不要用系统猜测替代用户事实。
- 营养资料不足：保留食物与分量，必要时在 `diet notes:` 标注估算不确定性；不制造精确到看似可靠的整日宏量值。

## 6. 测试与证据

已覆盖的最小边界包括：

- A：普通重量组；B：自重组；C：完全相同结构的紧凑 Complex Set；D：不等结构 `sets:` Complex Set；E：相邻重量不误判 Complex Set；F：显式 Superset；G：相邻动作不推断 Superset；H：动作 Notes；I：Training Notes；J：覆盖式修正词；K：新增式补录词；L：动态已登记字段；M：未登记字段边界；N：不添加默认有氧；O：省略有氧；P：相对日期规则。

本轮实际新增/执行的确定性测试：

- `tools/llm_entry_prompt_regression_test.py`：动态 registry、v10 prompt 关键规则、ASCII 结构、普通/自重/Complex/Superset/Notes parser 边界。
- `tools/data_module_engine_test.py`：模板版本、动态目录、无个人数据、behavior contract。
- `tools/data_module_web_candidate_test.py`：candidate endpoint 返回 v10。
- `tools/complex_set_superset_test.py`：Complex/Superset canonical relation 与历史投影。
- `tools/notes_semantics_core_test.py`：Notes 作用域与保存/导出链；其中现有测试还暴露了 fixture dictionary 在保存后补写 `revision`/`updated_at` 的既有差异，未纳入本轮修改范围。

以下既有回归在当前候选基线仍未通过，均未由本轮模板改动引起的确定性失败：

- `data_module_formal_mirror_browser_e2e_test.py`：在既有数据模块交互流程中刷新页面时出现 HTTP 500，测试没有输出服务端栈；本轮已用独立镜像直接验证 `/api/health`、`/api/build-info` 和 `/api/data-modules/llm-template`，v10 内容和隔离标识正确。
- `regression_test.py` / `smoke_test.py`：当前候选环境的既有动作词典数量/期望动作 fixture 不满足测试前置条件。
- `data_module_cloud_extension_test.py`：正式来源的 Data Module integrity issues 阻断 Cloud payload；本轮没有解除该阻断，也没有触碰 Cloud 或正式数据。

研究结论采用 EXTEND：没有引入外部 parser 或 workout grammar。外部材料只用于确认“关系和动作记录应分开”“自然语言识别应进入确定性 canonical mapping”这两个方向；当前本地 registry → prompt → parser → Review → save → export 链才是 Fitness Ledger 的权威契约。

## 7. Review 边界与剩余事项

- LLM 是否每次都遵守模板仍受模型行为影响；本轮测试证明的是 prompt 契约和确定性 parser/save 边界，不是某个供应商模型的概率性输出质量。
- Parser 继续兼容全角 Complex/Superset 输入，这是历史粘贴兼容；v10 生成规则明确要求 ASCII，不把兼容输入误当作标准生成格式。
- 当前没有服务端多轮会话合并器；“覆盖/新增”规则要求 LLM 对话携带上一版完整当前状态。若未来需要跨会话自动合并，应另立有状态数据合同和 Review 设计，不能仅靠 prompt 声称完成。
- 本报告未改变人读 Review formatter 的显示语言；它继续使用 `kg`、`×` 等产品展示符号，和可复制的 ASCII 输入协议是两个不同层次。

## 8. 交付

本轮候选工作区已准备人工产品 review。新的隔离镜像应使用 `daily-entry-template-anonymous-persistent-fixture` build 标识；现有 `8770` 复杂组/超级组镜像不改、不重启、不覆盖。正式目录、正式服务和真实数据均未写入。
