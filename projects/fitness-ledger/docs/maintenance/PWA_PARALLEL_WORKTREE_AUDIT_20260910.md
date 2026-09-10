# PWA parallel Worktree audit — 2026-09-10

## Conclusion

There are two materially different PWA implementations in the local Worktrees;
they are not interchangeable revisions of the same small patch. The current
candidate now includes the reviewed PWA parity work; the structure-generalization
Worktree remains a divergent reference and is not copied into this candidate.

### Candidate Worktree

`D:\FitnessLedger\work\fitness-ledger-movement-progress-20260910`

- Branch: `codex/movement-progress-expansion-20260910`
- Base: `ef17c8be9f7c60adcdfaf55dfe1bc20799e20c68`
- The candidate PWA now includes the Training Note-first homepage, optional
  Session Theme selection, session-based Training Archive and read-only session
  detail, active/inactive body-part modules, Glutes/Cardio mapping, movement
  dictionary ordering, and movement-history candidate lookup.
- It preserves same-day sibling sessions and uses persisted session IDs rather
  than inferring themes from the legacy `Split` field.
- Its current cache marker is `fitness-ledger-pwa-v40` / `20260910-04`.
- Candidate verification includes the static contract, session semantics,
  browser route smoke checks, body-record summary compatibility, candidate
  detail anchoring, and homepage Theme toggle behavior.

### Structure-generalization Worktree

`D:\FitnessLedger\work\fitness-ledger-structure-generalization-20260907`

- Branch: `codex/fitness-ledger-structure-generalization-20260907`
- Commit: `820da76b6042fcc0c831844d760402c886cc272a`
- Its PWA is a different earlier direction: Session Theme selection, theme
  reference history, and theme-derived training workbench UI.
- It has materially different `mobile_viewer/pwa/app.js`, `styles.css`,
  `mobile_viewer/app.py`, `data_access.py`, and PWA documentation.
- It does not contain the current body-part archive implementation and is not a
  safe source for selective copying without a new compatibility review.

## Release decision

Do not merge or copy the structure-generalization PWA version into the current
candidate. The candidate PWA changes are included in the reviewed scope and
are ready for the remaining formal closeout gates, subject to the final test,
formal-directory, service-health, and user-acceptance checks.

The parity checklist is:

1. session-theme catalog and active/inactive/pinned ordering;
2. multiple sessions on one date and the `2` date indicator;
3. movement category active/inactive state, including Glutes and Cardio;
4. movement dictionary ownership and movement-history lookup;
5. export/import and read-only API contracts;
6. PWA browser, contract, production-bundle, and formal-share tests.

The structure-generalization Worktree is a divergent earlier implementation;
it remains out of scope for the candidate and must not be selectively copied.
