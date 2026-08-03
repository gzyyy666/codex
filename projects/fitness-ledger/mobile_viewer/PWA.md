# Fitness Ledger Mobile Workbench PWA

`pwa/` is a mobile-first, read-only presentation layer for the existing
Fitness Ledger data. It intentionally keeps the formal ledger and the
CloudBase replica unchanged.

## Local preview

From the repository root:

```powershell
python start_mobile_viewer.py
```

Open `http://127.0.0.1:5055/pwa/`. The local Flask viewer exposes the same
read-only `/api/today` and `/api/training/<date>` endpoints used by the PWA.
Installability on a phone still requires an HTTPS deployment; localhost is
only for development.

## Deployment contract

The static files can be deployed to CloudBase Static Hosting, Cloudflare
Pages, or another HTTPS static host. No custom domain is required for a
private pilot: the provider's default HTTPS address is sufficient for Safari's
"Add to Home Screen" flow.

The deployed page must reach a safe Web API. The browser must not call the
WeChat-only `wx.cloud.callFunction` API and must not contain CloudBase secrets.
The API should expose the same read-only shape as the local viewer:

```text
GET /api/today
GET /api/training/<YYYY-MM-DD>
GET /api/search?q=<query>
```

Responses may be raw JSON or the existing `{ok: true, data: ...}` envelope.
The tracked `config.js` contains only a public same-origin default. Change its
`apiBaseUrl` at deployment time only when the reviewed Web API uses a different
same-origin or HTTPS base URL; never put credentials in it.

## Authentication boundary

The current Mini Program uses WeChat `openid` inside the `ledgerRead` cloud
function. Safari does not inherit a WeChat Mini Program session. Therefore a
standalone PWA needs a separately reviewed Web authentication/API gateway
before it can read private CloudBase data. This PWA does not weaken that
boundary, guess an openid, or add a write path.

The safe rollout order is:

1. Deploy and verify the read-only UI with a Web API gateway.
2. Confirm the gateway authenticates the same user and only returns the
   sanitized read replica.
3. Add Web-origin/security configuration and CORS rules.
4. Only then consider a separately reviewed write command for check-in.

## iPhone install

Open the HTTPS PWA URL in Safari, choose Share, then Add to Home Screen. If
the browser offers "Open as Web App", enable it for the standalone layout.
