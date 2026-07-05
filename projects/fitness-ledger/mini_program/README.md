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
