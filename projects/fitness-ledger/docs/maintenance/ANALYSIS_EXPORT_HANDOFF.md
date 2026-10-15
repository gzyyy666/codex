# Analysis Export Web Handoff

Status: integrated into the local Web business flow; AnalysisExportRequest v1.1 remains frozen.

## Resume point

- Preview: `http://127.0.0.1:8766/#tools?panel=export`
- Page renderer: `web_desktop/frontend/app.js` -> `analysisExportProtocolPage()`
- Page styles: `web_desktop/frontend/styles.css` -> `.analysis-export-*`
- Shared navigation: `web_desktop/frontend/index.html`; do not copy or restyle it from the export page.
- Service routes: `/api/analysis-export/v1/validate`, `/preview`, `/export`, `/artifact/...`, and `/natural-language/preview`.

## Product contract

The page is a natural-language-first, local read-only evidence workbench. Natural language is the default mode. JSON is secondary, appears only after mode selection, and starts blank; `Load example` is explicit and does not populate the editor automatically.

Both modes use the same real flow:

`describe -> validate -> confirm scope -> preview -> confirm -> export`

The right-side stage orb is the only process indicator. Its real states are request, validate/loading, scope, preview, done, and error. Errors preserve the input and explain what needs changing. Natural-language planning, candidate movement selection, multi-request batches, and preview revalidation must remain server-backed; the UI must not fabricate plans, records, fields, counts, or analysis conclusions.

## Safety boundaries

- Preserve AnalysisExportRequest v1.1 and its Validator semantics.
- Keep the maximum of 8 datasets per request and preserve real multi-batch semantics.
- Formal data is local-only and read-only: no upload, write, delete, or raw-data export.
- Do not change `data/tracker.json` or `data/movement_dictionary.json` for UI work.
- Do not route the old Shadow Planner or an unreviewed model into this page.
- Keep navigation and other first-level pages unchanged.

## Verification

Select checks by the actual changed boundary using `REGRESSION_CHECKLIST.md`.
The list below covers protocol/materialization/runtime changes, not an isolated
wording/style fix. Use temporary data for source tests. Source-only work does
not require formal runtime tests or publication.

For runtime diagnosis or authorized formal export verification, start with:

```powershell
python tools/project_status.py --write --json
```

For affected contracts, choose relevant suites from:

```powershell
node --check web_desktop/frontend/app.js
python tools/analysis_export_protocol_web_test.py
python tools/analysis_export_request_protocol_test.py
python tools/analysis_export_materializer_test.py
python tools/restricted_export_integration_test.py
python tools/formal_readonly_export_binding_test.py
python tools/formal_natural_language_runtime_test.py
```

Inspect the affected page/state and relevant layout breakpoints. Expand to
loading/error, invalid JSON, candidate selection, multi-batch and reduced-motion
cases when those behaviors can change. The 1920/1440/1280/1024/~768px widths are
useful layout coverage, not a per-edit quota. Broader UI suites are appropriate
for shared navigation, stage flow or layout changes.

## Closure and handoff

Use current `AGENTS.md` and the closeout guide for source-only, Review Deployment
and final release authorization. Honor equivalent explicit scope and permission
already given instead of demanding an exact phrase. A reviewed diff/commit is
sufficient for unpublished source work. Never copy formal `data/` into Git.

Future sessions follow `AGENTS.md` and read the relevant part of this handoff
for Analysis Export; use runtime status only when that boundary is relevant.
