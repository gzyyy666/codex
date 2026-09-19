# PWA 静态托管缓存故障复盘 — 2026-09-19

## 事件结论

本次不是 CloudBase 上传目标错误。静态文件确实上传到了正式地址：

`https://cloud1-d9g35v5s1a904a8ad-1450570992.tcloudbaseapp.com`

但手机端仍可能继续运行旧 PWA，原因是静态 CDN 对不带查询参数的 Service Worker URL
保留了长时间缓存。CLI 返回“31/31 文件上传成功”只证明上传请求成功，不证明手机已经取得新
Service Worker 或新缓存。

## 可复现证据

- 无参数 `sw-blur-height-fix.js` 仍返回旧的 `fitness-ledger-pwa-v73`。
- 该响应带有 `Cache-Control: max-age=31536000` 和较大的 `Age`，说明边缘缓存没有因为重新上传
  自动失效。
- 加查询参数的 Service Worker URL 能返回新的缓存名；根入口也必须加载带查询参数的新前端脚本，
  否则旧页面不会注册新的 URL。
- CloudSync 数据副本本身另行回读为 `SYNCED`；静态资源缓存问题不能用 CloudSync 状态代替判断。

## 根因

发布流程只验证了静态托管 CLI 的上传结果，没有验证完整的手机加载链：

`index.html → active app script → serviceWorker.register() → APP_SHELL`

其中 Service Worker 注册路径保持不变，CDN 又对旧路径设置了长期缓存，导致上传后的新缓存名
无法被手机及时发现。

## 当前修复

PWA `1.1.34` 使用以下发布约束：

1. 根入口加载 `app-blur-height-fix.js?v=20260919-03`。
2. 前端注册 `sw-blur-height-fix.js?v=20260919-03`。
3. Service Worker 缓存名提升为 `fitness-ledger-pwa-v76`。
4. 状态页以产品化版本徽标显示 `1.1.34`，不展示 commit、缓存名等技术细节。

## 下次发布检查清单

1. 运行 `python tools/pwa_deployment_preflight.py --deployment`。
2. 上传后直接请求正式根入口，检查它实际引用的 app script 查询版本。
3. 请求该 app script，确认版本号、新的 Service Worker 查询版本均存在。
4. 请求带查询版本的 Service Worker，确认缓存名已提升；不要只看上传 CLI 输出。
5. 用手机正式链接刷新，再进入“同步与档案”查看用户可见版本号。
6. 若桌面图标仍使用旧缓存，关闭并重新打开；仍未切换时删除旧图标，再从正式链接重新添加。
7. 另行检查 `/api/pwa/read` 的登录保护和 CloudSync 的 `SYNCED + cloud_verified`，不要把静态
   发布状态、接口鉴权状态和数据同步状态混为一个结论。

## 检索关键词

`PWA CDN cache`、`Service Worker stale`、`CloudBase hosting deploy`、`cache-busting`、
`sw-blur-height-fix.js`、`APP_SHELL`、`手机仍显示旧版本`、`上传成功但 PWA 未更新`。
