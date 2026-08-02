# Fitness Ledger Mini Program Preparation

This is a read-only WeChat Mini Program for gym-side reference. It does not contain CloudBase credentials or personal data in tracked source files.

## Primary Mobile Flow

1. Choose shoulders, chest, back, legs, or arms.
2. Compare each movement's latest session, previous session, and historical best.
3. Open a movement only when the full trajectory is needed.
4. Daily diet and training prose stays collapsed until the user explicitly expands it.

The Mini Program never writes back to the formal Fitness Ledger database.

## Open In WeChat DevTools

1. Import this `mini_program` directory.
2. Use the test AppID for layout review, or replace `touristappid` in `project.config.json` with your own AppID.
3. Copy `miniprogram/config/env.example.js` to `miniprogram/config/env.local.js` and fill in `envId`.
4. Deploy `cloudfunctions/ledgerRead` to the same CloudBase environment.
5. Call the Data Status page once to obtain your openid, then set the cloud function environment variable `FITNESS_LEDGER_ALLOWED_OPENIDS` to that openid.
6. After changing `cloudfunctions/ledgerRead/index.js`, redeploy `ledgerRead` with cloud dependencies installed.

The program has no write controls. Every page displays its read-only status and latest replica timestamp.

## Accepted freeform note baseline

The current accepted Mini Program build marker is `v2026.08.02-action-candidates-12`.
Training Reference includes a neutral `TRAINING NOTE` surface and a floating
Dock that share the local-only Storage key
`fitness-ledger:freeform-notepad:v2:current-training`. The note accepts free
text and is never written to CloudBase, `fl_training_sessions`,
`fl_movement_history`, `fl_movements`, or the formal JSON data.

Both the inline Archive editor and the scroll-revealed Dock persist on input.
When the user switches tabs, the Reference page refreshes its mirror from
Storage instead of saving a stale page buffer over the Dock's newer text. The
Dock's fixed textarea is intentionally not nested inside another `fixed`
textarea mode.

While typing, the Reference page may recognize catalog names, English names,
and aliases and surface a neutral floating read-only history panel. The panel
does not change the note, does not depend on the selected body part, and does
not write a formal record. It keeps a fixed viewport: the latest session is
visible initially, older sessions are available by scrolling, and the collapsed
state is a narrow edge tab. The movement order shown in a preview comes from
the read-only history data, not from parsing the note.

For future changes, preserve this local-only, read-only boundary and manually
verify: Dock input -> collapse/reopen -> candidate panel -> switch to Status ->
return to Training Reference. Automatic formal-record writes are not part of
this baseline.
