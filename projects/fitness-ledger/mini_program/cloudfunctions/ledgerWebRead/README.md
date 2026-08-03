# ledgerWebRead

独立的 PWA 只读云函数。它复用 CloudBase 中已经同步的十个
`fl_*` 只读集合，但不复用小程序 `openid` 认证边界，也不写入任何集合。

## HTTP 配置

建议在 CloudBase HTTP 网关绑定：

```text
云函数：ledgerWebRead
触发路径：/api/pwa/read
方法：GET、OPTIONS
```

开启 HTTP 身份认证，只允许已登录的网页用户访问。函数默认要求
`Authorization: Bearer <accessToken>`，因此不能被匿名请求直接读取。

配置以下环境变量：

```text
FITNESS_LEDGER_WEB_AUTH_REQUIRED=true
FITNESS_LEDGER_WEB_ORIGINS=https://cloud1-d9g35v5s1a904a8ad-1450570992.tcloudbaseapp.com
```

`FITNESS_LEDGER_WEB_ORIGINS` 只填写实际 PWA 来源；多个来源用英文逗号分隔。

## 本地部署检查

该函数必须单独部署，不要覆盖现有的 `ledgerRead`。它只支持读操作，
不包含 `add`、`update`、`set` 或 `remove`。

## 读取接口

接口动作与小程序 `ledgerRead` 保持一致，包括 `status`、`latest`、
`bodyAreas`、`bodyArea`、`trainingRecords`、`movementCatalog`、
`movementHistory`、`recordDetail` 和 `trainingDayDetail`。
