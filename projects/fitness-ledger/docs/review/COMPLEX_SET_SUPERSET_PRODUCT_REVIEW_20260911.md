# Complex Set + Session Superset 产品 Review

日期：2026-09-11
状态：候选镜像可审查，不代表正式发布

## 一句话结论

当前候选版本已经把“复杂组”和“Session 内超级组”接入 Daily Entry →
Review → Confirm & Save → Training / Movement History / Export 的完整链路；
`胸肩` 这样的 Session Theme 会同时出现在已有的“胸”和“肩”主题中。

## 产品层可见效果

### 1. 直接录入复杂组

推荐给 LLM 的完整 Daily Entry 格式：

```text
date: 2026-09-11
training: 胸肩

 3. y举
 (7.5+5)-(6+8)-3
```

系统展示为：

```text
7.5kg × 6 + 5kg × 8 × 3组
```

含义是每组依次完成两个 segment，共 3 组；容量为 255 kg·reps。
它不会被拆成两个普通动作，也不会把 7.5kg 当成唯一的进步重量。

复制过程中即使动作缩进丢失，或用户使用中文全角标点，候选镜像也能进入
训练 Review，而不会误打开“建立新的记录项”数据模块窗口：

```text
3. y举
（7.5＋5）－（6＋8）－3
```

### 2. 每组不同的复杂组

```text
sets: 7.5x6+5x8; 7.5x6+5x7; 7.5x5+5x8
```

每个分号是一组，系统不会错误压缩为 `×3`。

### 3. Session 内超级组

```text
 1. Incline Press
 60-8-3

 2. Triceps Pushdown
 30-12-3

 superset: A = movement 1, movement 2
```

产品表现：

- 两个动作仍然是独立动作和独立历史。
- 两个动作各自显示 `[超级组 A]`。
- Movement History 显示关系成员，例如 `超级组 A · Triceps Pushdown`。
- 仅相邻动作不会自动被推断为超级组。

### 4. 多主题 Session

输入：

```text
training: 胸肩
```

当主题目录中已有“胸”和“肩”时，同一条完整 Session 会同时进入：

- 胸 → Training Records
- 肩 → Training Records
- ALL RECORDS

系统保留原始标签 `胸肩`，并另外保存解析后的主题 ID 列表作为归档关系。

### 5. 没有主题或主题不存在

- 没有填写主题：Session 仍然完整保存，进入 ALL / 未命名训练。
- 目录锁定且无法匹配：不丢记录，不静默创建，保留原始标签和 Review 提示。
- 正常可编辑目录下出现新的非空主题：沿用既有兼容逻辑创建新的 Session Theme。
- `胸肩手臂` 只有在已有主题能够完整且无歧义拆分时才会多主题归档。
- 歧义或格式错误不会自动猜测，需用户在 Review 中修正。

## 用户体验链路

```text
自然语言 / LLM 输出
        ↓
Daily Entry 输入板
        ↓
结构识别：动作、复杂组、主题、超级组
        ↓
Review：查看 segment、主题和关系
        ↓
Confirm & Save
        ↓
Training Archive / Movement History / PWA / Export
```

## 产品决策与边界

| 项目 | 当前决策 |
|---|---|
| 复杂组 | 一个 Set 内的有序 segment，不是多个普通 Set |
| 超级组 | Session 内独立动作之间的显式关系，不是新动作 |
| 关系识别 | 只接受明确的 `superset: A = movement 1, movement 2` |
| 进步统计 | 复杂组保留容量和次数，但不伪造单一重量趋势 |
| 原始记录 | 始终保留，结构化字段是可验证投影 |
| PWA / Mobile | 保留原始训练记录和轻量关系提示；不在本轮增加复杂编辑器 |
| Cloud / Analysis Export | 只扩展读取字段，不改变既有请求语义；本轮未发布 |

## 人工验证入口

候选镜像：

[打开本地候选镜像](http://127.0.0.1:8770/#quick)

匿名浏览器证据：

- [复制粘贴后的 Review](C:\Users\26087\.codex\visualizations\2026\09\11\01a08fdf-80a7-7d82-9c93-1585913987bf\followup\complex-set-review.png)
- [胸主题页面](C:\Users\26087\.codex\visualizations\2026\09\11\01a08fdf-80a7-7d82-9c93-1585913987bf\followup\superset-session-chest-theme.png)
- [肩主题页面](C:\Users\26087\.codex\visualizations\2026\09\11\01a08fdf-80a7-7d82-9c93-1585913987bf\followup\superset-session-shoulders-theme.png)
- [动作历史与超级组上下文](C:\Users\26087\.codex\visualizations\2026\09\11\01a08fdf-80a7-7d82-9c93-1585913987bf\followup\complex-set-history-and-superset-context.png)

建议产品 Review 顺序：

1. Quick → 粘贴上面的全角标点片段，确认进入 Review 而不是数据模块表单。
2. Training → 分别打开“胸”和“肩”，确认是同一条完整 Session。
3. Movements → Incline Press，确认复杂组没有伪造单一重量趋势。
4. 查看 Review 中的 `[超级组 A]` 和关系成员。

## 当前候选边界

- LLM 模板会输出 ASCII 半角结构格式；解析器额外兼容常见全角标点。
- 动作名称仍需能匹配动作字典或在 Review 中确认新动作。
- 当前不生成 A1/A2 执行时间线，也不推断疲劳、效率或因果关系。
- 本报告及候选实现未修改正式 tracker、Cloud、Mini 或正式服务。

关联维护说明：

[Complex Set + Session Superset 适配说明](../maintenance/COMPLEX_SET_SUPERSET_ADAPTATION_20260911.md)
