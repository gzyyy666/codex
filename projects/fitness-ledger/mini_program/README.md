# Fitness Ledger Mini Program Preparation

This is a read-only WeChat Mini Program skeleton. It does not contain an AppID, CloudBase environment ID, credentials, or personal data.

## Open In WeChat DevTools

1. Import this `mini_program` directory.
2. Use the test AppID for layout review, or replace `touristappid` in `project.config.json` with your own AppID.
3. Copy `miniprogram/config/env.example.js` to `miniprogram/config/env.local.js` and fill in `envId`.
4. Deploy `cloudfunctions/ledgerRead` to the same CloudBase environment.
5. Call the Data Status page once to obtain your openid, then set the cloud function environment variable `FITNESS_LEDGER_ALLOWED_OPENIDS` to that openid.

The program has no write controls. Every page displays its read-only status and latest replica timestamp.
