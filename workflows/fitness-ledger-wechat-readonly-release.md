# Fitness Ledger WeChat Read-Only Release

Use this workflow after changing the Mini Program UI, `ledgerRead`, or the disposable cloud replica.

## Boundaries

- Local JSON remains authoritative.
- The Mini Program and `ledgerRead` never write Fitness Ledger records.
- Never commit `env.local.js`, OpenIDs, personal payloads, or CloudBase credentials.
- Keep the user-controlled OpenID allowlist in the deployed cloud-function environment variable `FITNESS_LEDGER_ALLOWED_OPENIDS`.

## Source Validation

From the local Fitness Ledger project:

1. Run `node --check mini_program/cloudfunctions/ledgerRead/index.js`.
2. Run JavaScript syntax checks for Mini Program pages.
3. Run `python tools/mini_program_test.py`.
4. Run `python tools/cloud_payload_test.py` when payload generation or collection contracts change.

## Cloud Function Deployment

1. Open the project in WeChat DevTools.
2. Right-click `cloudfunctions/ledgerRead`.
3. Choose cloud install/deploy with dependencies.
4. Confirm the active CloudBase environment is the intended environment.
5. Do not replace or remove `FITNESS_LEDGER_ALLOWED_OPENIDS` during redeployment.

## Replica Refresh

1. In Web Export, open the quiet Cloud Sync workbench.
2. Generate and locally validate the ten-collection package.
3. Import non-meta collections in the manifest order, using full replacement.
4. Import `fl_meta` last.
5. Copy/export the resulting single `fl_meta` row and run post-sync verification in the Web workbench.
6. A passing report requires matching schema, generation timestamp, and collection counts. It does not authorize cloud writes from the Mini Program.

## Mobile Acceptance

1. Home shows shoulder, chest, back, legs, and arms with nonzero counts where history exists.
2. The Training tab opens the body-area archive rather than a text-search form.
3. Selecting a body area shows movement cards with latest, previous, best, and trajectory actions.
4. The body-area screen switches between movement-first and related-training-day views.
5. Pinned movements appear before normal frequency ordering.
6. Training and Reference show the cloud generation time/latest record date and warn quietly when older than 48 hours.
7. A bodyweight movement such as pull-up still shows its set history.
8. Today and record details keep long text collapsed until explicit expansion.
9. Search results show clean titles rather than concatenated search-index blobs.
10. Status remains read-only and identity diagnostics return no private Fitness Ledger data.

## Recovery

Use the latest tested Git commit or the tag created for the Mini Program checkpoint. Restore source only; never restore live personal JSON from the public repository.
