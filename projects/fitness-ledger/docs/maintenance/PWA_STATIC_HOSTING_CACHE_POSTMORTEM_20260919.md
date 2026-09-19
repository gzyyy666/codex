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

## 追加发现：静态资源会出现“混合版本”

后续验证还发现，即使入口脚本已经切换到新版本，未带查询参数的 CSS 仍可能从 CDN 或旧
Service Worker 缓存中返回旧文件。手机上会表现为：页面功能和版本号已经更新，但版本徽章仍像
普通文本一样没有样式。这不是 UI 结构本身失效，而是 `index.html`、JS、CSS、manifest 和
Service Worker 没有作为同一个版本组一起切换。

因此，发布时必须让入口脚本、主 CSS、manifest、manifest 的 `start_url`、Service Worker
注册地址和 Service Worker 的 `APP_SHELL` 同时使用新的查询版本；只提升 JS 或只看到上传成功都
不能证明手机得到的是完整的新页面。

## 当前修复

PWA `1.1.37` 使用以下发布约束：

1. 根入口加载 `app-blur-height-fix.js?v=20260919-06` 和
   `styles-blur-height-fix.css?v=20260919-06`。
2. 前端注册 `sw-blur-height-fix.js?v=20260919-06`。
3. Service Worker 缓存名提升为 `fitness-ledger-pwa-v79`。
4. 三套 manifest 的 `start_url` 同步提升为 `./?v=20260919-06`，避免桌面图标继续启动旧入口。
5. 状态页仅以轻量浅色文字显示 `1.1.37`，不展示 commit、缓存名等技术细节。

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
