# Fitness Ledger PWA 部署与手机桌面安装

## 先说结论

当前 `mobile_viewer/pwa/` 已部署到 CloudBase 静态托管，生产配置通过启用身份认证
和安全域名检查的 HTTP 网关访问独立只读函数 `ledgerWebRead`。匿名接口实测返回
`401 Unauthorized`，不会直接暴露训练数据。

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

当前上线状态：

- 静态站点：`https://cloud1-d9g35v5s1a904a8ad-1450570992.tcloudbaseapp.com`
- API 路由：`/api/pwa/read` → `ledgerWebRead`
- HTTP 身份认证：开启
- 安全域名：开启；静态站点域名已在安全域名列表
- 生产 PWA：`requireWebAuth: true`
- 匿名访问：已验证返回 `401 Unauthorized`

后续仅需由实际用户在手机上验证账号登录和真实数据展示。

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

## 仍需用户完成的验收

- 在 CloudBase“登录方式”中确认账号密码登录已启用；不要把密码写进代码或发给他人。
- 用现有 `administrator` 网页账号登录 PWA，确认最新训练日、动作候选、动作历史和
  状态页均能读取。
- iPhone Safari 打开静态站点，选择“分享”→“添加到主屏幕”→“作为 Web App 打开”。

现有小程序 `ledgerRead`、正式数据集合和同步流程没有被此次 PWA 网关部署修改。
