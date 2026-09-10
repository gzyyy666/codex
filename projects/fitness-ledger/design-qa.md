# PWA Homepage Visual Convergence QA

## Source visual truth

- Neutral: `D:\a\ChatGPT Image 2026年9月10日 16_55_37 (1).png`
- Selected + collapsed: `D:\a\ChatGPT Image 2026年9月10日 16_55_37 (2).png`
- Selected + expanded: `D:\a\ChatGPT Image 2026年9月10日 16_55_38 (3).png`
- Source pixels: 863 × 1822 each; source includes phone system chrome.

## Implementation evidence

- URL: `http://127.0.0.1:5055/pwa/#reference`
- Neutral: `D:\FitnessLedger\review-artifacts\pwa-visual-convergence-20260910\actual-neutral-390x844.png`
- Selected + collapsed (Arms): `D:\FitnessLedger\review-artifacts\pwa-visual-convergence-20260910\actual-selected-collapsed-390x844.png`
- Selected + expanded (Back): `D:\FitnessLedger\review-artifacts\pwa-visual-convergence-20260910\actual-selected-expanded-390x844.png`
- Additional viewport captures: `actual-*-393x852.png`
- Browser: Edge headless via Playwright, device scale factor 1.
- CSS viewport: 390 × 844 and 393 × 852.
- Body overflow check: `scrollWidth === clientWidth` at both viewports.
- For combined comparison inputs, each source was fit to 390 × 844 and placed beside the same-state implementation capture:
  - `comparison-neutral-390x844.png`
  - `comparison-selected-collapsed-390x844.png`
  - `comparison-selected-expanded-390x844.png`
- System status bar and home indicator were excluded from implementation; source-only chrome was not used as a pass/fail criterion.

## State coverage

- Neutral: `selectedThemeId = null`, `archiveExpanded = false`; only movement placeholder is shown.
- Selected + collapsed: Session Theme is selected from `session_themes`; whole-page palette changes; only theme summary is shown.
- Selected + expanded: `archiveExpanded = true`; note becomes compact; movement archive cards become primary; session history is secondary and collapsed.
- Selected collapsed capture uses `arms`; expanded capture uses `back`, matching the supplied reference states' visual theme intent.

## Neutral reference checklist

1. Header independent from card — PASS
2. “训练首页。” outside the note — PASS
3. Header occupies a distinct first section — PASS
4. Note top position is separated by a deliberate gap — PASS
5. Note width is inset from viewport edges — PASS
6. Paper outline is visible — PASS
7. Rear paper layers are visible — PASS
8. Layered note shadow is visible — PASS
9. Note forms the main hero object — PASS
10. Footer actions sit at the note bottom — PASS
11. Theme pills are lightweight — PASS
12. Neutral pills are all inactive — PASS
13. Movement area is a light placeholder only — PASS
14. Background has low-saturation layered geometry — PASS
15. Background decoration stays below text weight — PASS
16. No right-side body overflow — PASS
17. Page no longer reads as an admin/form screen — PASS
18. Training Note is the first visual business object — PASS

## Selected collapsed checklist

- Header geometry retained — PASS
- Arms palette changes page atmosphere, note tint, pills and preview border — PASS
- Summary shows theme name, movement count and recent training date — PASS
- Session history and movement cards remain hidden — PASS
- No horizontal body overflow — PASS

## Selected expanded checklist

- Header geometry retained — PASS
- Note switches to compact utility mode — PASS
- Movement archive becomes the primary information region — PASS
- Movement cards show real Back data — PASS
- Sort controls are grouped and styled — PASS
- Session history is preserved as secondary collapsed content — PASS
- Back palette changes the page atmosphere — PASS

## Comparison history

### Pass 1 — blocked

- Finding: page header and note were mixed into one large form-like card; neutral movement area was too heavy; expanded session history visually preceded movement cards.
- Fix: introduced `home-header`, `note-stack`, `note-sheet`, `theme-strip`, `movement-preview`, and explicit home state attributes; moved session history below movement cards.

### Pass 2 — passed

- Finding: header typography inherited the legacy serif rule; compact expanded note was overridden by a later legacy selector; the expanded capture could retain the clicked scroll position.
- Fix: added final scoped homepage overrides, compact-note specificity, and reset viewport on archive toggle.
- Evidence: final captures listed above; scroll width equals client width at both required viewports.

## Automated checks

- `node --check mobile_viewer/pwa/app.js` — PASS
- `python -m py_compile mobile_viewer/app.py` — PASS
- `python tools/pwa_static_test.py` — PASS
- `python tools/data_module_pwa_local_test.py` — PASS
- `node tools/data_module_pwa_contract_test.js` — PASS
- `git diff --check` — PASS (line-ending warnings only)

## Follow-up P3

- The supplied references contain dynamic note text and phone system chrome. The implementation intentionally keeps note content data-driven and does not hardcode the reference's example training note or fake system chrome.

final result: passed
