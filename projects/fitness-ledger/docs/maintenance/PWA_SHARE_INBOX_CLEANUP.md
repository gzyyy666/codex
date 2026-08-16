# CloudBase 当日训练记录清理

`fl_web_share_inbox` 是手机到桌面的临时传输集合，不是正式训练档案。

## 保存和读取

- 手机登录后，第二次确认才写入 CloudBase 私有集合。
- 电脑端使用同一 CloudBase 账号读取最近记录。
- 手机和电脑都不负责删除历史记录；它们只读取最近 7 条用于展示。
- 云端按账号只保留最新 7 次上传记录，不按 30 天计算。

## 云端定时清理

本仓库提供并已部署的函数：

`cloudfunctions/fl_web_share_inbox_cleanup/`

它每天按账号和 `received_at` 排序，删除每个账号超过最近 7 次的旧文档，删除动作在 CloudBase 云函数中执行，不依赖手机是否在线或页面是否打开。

配置样例见：

`cloudbaserc.share-inbox.example.json`

当前环境已部署同名 Node.js 云函数，并创建每日定时触发器。触发器使用 7 段 Cron，每天 03:00：

`0 0 3 * * * *`

部署前确认控制台显示的时区，并确认函数拥有读取、删除 `fl_web_share_inbox` 的服务端权限。

## 安全边界

- 集合规则仍使用“读取和修改本人数据 [PRIVATE]”。
- 客户端不提交或选择 `_openid`；CloudBase 自动写入当前登录用户。
- 清理函数只处理每个账号超出最近 7 次的传输项；没有 `_openid` 的异常文档不会被混入其他账号的清理范围。
- 函数没有写入 `fl_daily_records`、`fl_data_module_records` 或其他正式档案集合。

本次部署没有修改正式训练数据集合；清理函数首次手动检查结果为 0 条扫描、0 条删除。
