# Fitness Ledger Mobile Workbench PWA

`pwa/` is a browser implementation of the existing Mini Program surface. It
keeps the same three tab pages (训练部位档案、训练记录、同步与档案), secondary
body/diet archives, record detail, movement trajectory, local Training Note,
candidate recognition, and read-only navigation. It intentionally keeps the
formal ledger and the CloudBase replica unchanged.

## Sealed Mini Program parity

The PWA interaction baseline follows the Mini Program sealed commit
`23057d674e73a21048401c2fb5548c25bfa05f32`: the Training Note remains local-only,
candidate recognition stays in a neutral overlay, candidate clicks open an
in-place read-only movement history sheet, and the collapsed Dock appears after
the archive header has scrolled away. To match the approved PWA behavior, a
note containing several movement names displays only the last recognized
movement; its preview and detail sheet still show the latest formal history,
set order markers, and notes. The mobile layout uses the Mini Program's 750rpx
spacing baseline converted to the viewport, with a 16px minimum editor font to
avoid iPhone input zoom.

The PWA Training Note is intentionally a local scratchpad. Its input is not
recreated for every keystroke: Chinese composition events are allowed to
finish, English cursor position stays in the same textarea, and the candidate
overlay is refreshed independently. Candidate history is read-only data from
the same CloudBase replica used by the rest of the PWA.

## Data and Sync boundary

The PWA does not replace or extend the existing Cloud Sync automation. The
normal flow remains:

```text
formal local data → Cloud Sync export/payload → CloudBase fl_* replica → PWA read-only API
```

When the optional Data Module registry is enabled, the same sync run also
includes `fl_data_modules`, `fl_data_module_records`, and the compact contract.
The phone PWA reads only the sanitized module definition and value fields:
raw input, notes, definition snapshots, and source hashes stay excluded.

Placement follows the desktop definition without adding a new top-level tab:

- Body, Diet, and Training modules join their existing dated archive cards and
  daily detail sections. A module-only date still creates a readable archive
  card, so a Diet or Training metric is not hidden merely because the native
  collection has no row for that day.
- A module assigned to another category appears under `其他记录` in the daily
  detail. If its surface is `page_widget`, its latest value also appears as a
  compact edge control on the selected page.
- `history_only` remains available in daily detail; `record_only` is not
  automatically rendered. Retired modules keep historical values but do not
  create a current page widget.

The one-click sync command needs no change for this PWA release. Run it as
before when formal data changes; after the upload and verification complete,
the PWA will read the new `fl_*` records on its next load. The local Training
Note itself is not uploaded, and typing a movement name does not create a
formal training record.

## Local preview

From the repository root:

```powershell
python start_mobile_viewer.py
```

Open `http://127.0.0.1:5055/pwa/`. The local Flask viewer exposes
`/api/pwa/read?action=...` using the same action vocabulary as the Mini
Program's `ledger.call(...)` service.
Installability on a phone still requires an HTTPS deployment; localhost is
only for development.

## Deployment contract

The static files can be deployed to CloudBase Static Hosting, Cloudflare
Pages, or another HTTPS static host. The complete phone experience also needs
a reviewed Web API gateway and Web authentication; static hosting alone only
serves HTML/CSS/JavaScript. See `PWA_DEPLOYMENT.md` for the current checklist
and run `python tools/pwa_deployment_preflight.py` before uploading.

CloudBase's default HTTPS address is suitable for an initial private test when
the console permits it. For production browser access, follow the current
CloudBase hosting/domain requirements and configure a custom domain if the
platform requires one.

The deployed page must reach a safe Web API. The browser must not call the
WeChat-only `wx.cloud.callFunction` API and must not contain CloudBase secrets.
The deployed Web gateway should expose the same read-only action shape:

```text
GET /api/pwa/read?action=bodyAreas
GET /api/pwa/read?action=bodyArea&part=shoulders
GET /api/pwa/read?action=trainingRecords
GET /api/pwa/read?action=recordDetail&date=YYYY-MM-DD
GET /api/pwa/read?action=movementHistory&movementId=<id>
GET /api/pwa/read?action=dataModules
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
