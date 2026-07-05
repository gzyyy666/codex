# WeChat DevTools Preview Checklist

- [ ] Project opens from `mini_program/` without missing-page errors.
- [ ] Local `project.config.json` contains the intended AppID.
- [ ] Ignored `config/env.local.js` contains the intended CloudBase env_id.
- [ ] Ten replica collections exist and match `fl_meta.collection_counts`.
- [ ] `ledgerRead` is deployed to the same environment.
- [ ] `FITNESS_LEDGER_ALLOWED_OPENIDS` contains the testing account.
- [ ] Simulator opens Home and shows loading, empty, or real data cleanly.
- [ ] Today and Record Detail show only replica data.
- [ ] Training Reference returns history and never generates a plan.
- [ ] Search finds Chinese name, English name, alias, date, split, or diet keyword.
- [ ] Movement Detail shows recent history and notes.
- [ ] Network, unauthorized, empty, and stale-data messages are understandable.
- [ ] There is no entry, edit, Parse & Review, Undo, dictionary, or Data Check repair control.
- [ ] No secret, local absolute path, personal payload, or full raw text is committed.
- [ ] Real-device preview uses the intended environment and shows the latest sync timestamp.
