# Fitness Ledger PWA 部署与手机桌面安装

## 先说结论

当前 `mobile_viewer/pwa/` 是可以直接上传的纯静态 PWA，但本地配置中的
`/api` 只连接本机 Flask 查看器。把静态文件上传到 CloudBase 后，页面可以打开，
但如果没有 Web API 网关，训练数据不会加载。

现有 `mini_program/cloudfunctions/ledgerRead` 是小程序专用读取函数，使用
`wx.getWXContext()` 和微信 `openid` 白名单。不能把它未经改造直接当作 Safari
接口使用。PWA 需要单独的 Web 登录和只读 API 适配层；这个适配层不应修改小程序
封板函数的行为。

## 你需要额外准备的内容

必须准备：

1. 有权限访问当前 CloudBase 环境的腾讯云账号，并能在本机完成 `cloudbase login`。
2. 确认要使用的 CloudBase 环境 ID。当前最近一次真实同步和控制台部署使用的是
   `cloud1-d9g35v5s1a904a8ad`，仍以 CloudBase 控制台为最终准。
3. 一个 Web 登录方式。推荐启用 CloudBase Web 登录并使用微信 OAuth，或使用
   CloudBase 账号登录。微信小程序的登录会话不会自动继承到 Safari。
4. 将实际访问地址加入 CloudBase Web 安全来源/安全域名配置。
5. 一个 Web 只读 API 地址，接口需要覆盖 PWA 当前使用的 `pwa/read` action：
   `status`、`whoami`、`bodyAreas`、`bodyArea`、`trainingRecords`、
   `bodyRecords`、`dietRecords`、`recordDetail`、`trainingDayDetail`、
   `movementCatalog`、`movement`、`movementHistory`、`search`。

不一定要马上购买域名：CloudBase 静态托管可以先用平台默认 HTTPS 地址做开发/个人
测试。正式通过浏览器访问时，应按当前 CloudBase 控制台和文档要求配置自定义域名；
如果你已有域名，只需要 DNS 配置权限，不需要重新购买。

## 我已经准备好的部分

- PWA 静态资源已具备 `manifest.webmanifest`、`service worker`、图标和离线缓存。
- 资源使用相对路径，适合上传到静态托管根目录或 `/pwa/` 子路径。
- 当前 PWA 保持只读，不包含 CloudBase SecretId、SecretKey 或写入接口。
- `tools/pwa_deployment_preflight.py` 可以在上传前检查静态包、清单、相对路径和
  敏感配置。
- CloudBase 静态托管 CLI 的上传命令已确认，登录后可使用：

```powershell
cloudbase hosting deploy .\mobile_viewer\pwa / --env-id <环境ID>
```

这一步只上传静态页面，不会自动解决 Web 登录和数据 API。

## 安全上线顺序

当前断点：静态 PWA 已上传；`ledgerWebRead` 已作为独立 Event 云函数部署并处于
`Active / Available`，但尚未创建 HTTP 网关路由或触发器，所以没有公开数据入口。
下一步是完成安全来源和 Web 登录方式，再绑定 `/api/pwa/read`。

1. 先运行静态预检：

```powershell
python tools/pwa_deployment_preflight.py
```

2. 完成 Web 只读 API 和 Web 登录配置，并在浏览器中验证 `status`、
   `movementCatalog`、`movementHistory` 三个接口。
3. 将 PWA 的 `config.js` 中 `apiBaseUrl` 指向审查过的 Web API，并将
   `requireWebAuth` 设为 `true`；不要把密钥放入 `config.js`。
4. 登录 CloudBase 后上传静态文件。
5. 用 Safari 打开 HTTPS 地址，选择“分享”→“添加到主屏幕”→打开“作为 Web App
   打开”→“添加”。
6. 手机上验证登录、最新训练日、动作候选、动作历史和状态页；确认失败时不会
   回退显示本地或其他用户的数据。

## 当前不能自动替你完成的动作

- CloudBase 控制台登录和 OAuth/安全域名配置需要你的账号交互。
- `ledgerWebRead` 的代码已经准备在
  `mini_program/cloudfunctions/ledgerWebRead/`，需要在 CloudBase 单独部署并通过
  HTTP 网关暴露；它不会覆盖现有小程序 `ledgerRead`。
- 仍需要在 CloudBase 控制台配置 Web 登录方式、安全来源和 HTTP 网关权限；这些
  需要你的账号交互，不能凭猜测代替。
- 未完成 Web API 前不能宣称“手机桌面版已经具备小程序同样的数据功能”。
