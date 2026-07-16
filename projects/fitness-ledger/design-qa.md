# Design QA - Refined Movement Index

Date: 2026-07-06

## Evidence

- Source visual truth: `C:\Users\26087\Pictures\Screenshots\屏幕截图 2026-07-03 221209.png`
- Theme-art reference: `C:\Users\26087\Pictures\Screenshots\屏幕截图 2026-07-05 225247.png`
- Previous image-heavy implementation: `C:\Users\26087\Pictures\Screenshots\屏幕截图 2026-07-06 130732.png`
- Final implementation screenshot: `design-qa-implementation.png`
- Side-by-side comparison: `design-qa-comparison.png`
- Viewport: 1600 x 1000
- State: Movement Index, default archive view, live local data

## Full-view comparison

- The page retains the cream paper background, editorial heading, compact two-column archive density, search, movement count, and dictionary entry.
- Group panels use the approved five original body-area illustrations without filters or dark overlays.
- Each illustration is enlarged and centrally cropped so the athlete and exercise remain recognizable across at least 70% of the panel.
- Amber, coral, teal, violet, and blue come directly from the approved source artwork rather than a separate flat panel tint.

## Focused region comparison

- Back and shoulder panels were reviewed at original screenshot resolution.
- Lead cards are larger, warmer, and more elevated than medium- and low-frequency cards.
- Medium-frequency light-glass cards remain near 10% white opacity so the dominant figure and local underglow remain visible.
- Low-frequency dark-glass cards remain translucent, readable, and do not resemble disabled controls.
- Chinese names, English subtitles, session counts, and `Open trajectory` remain clear over every surface.

## Required fidelity surfaces

- Typography: unchanged editorial hierarchy; movement labels retain readable optical weight and truncation behavior.
- Spacing: existing compact archive matrix and two-column rhythm preserved.
- Colors: the cream editorial page remains global context; local body-area colors support the black-gray figure instead of replacing it.
- Image quality: existing approved local body-area artwork retained; no placeholder or code-drawn illustration introduced.
- Copy: no copy or data behavior changed.

## Patches made

- Removed grayscale, brightness, multiply, masking, and dark overlay treatments from the five source illustrations.
- Centered and enlarged the original artwork so the athlete is the panel's primary visual content.
- Reduced ordinary cards to 0.08 light glass and 0.18 dark glass while retaining a 0.82/0.74 translucent lead card.
- Established three card levels: translucent yellow lead card, light-glass medium-frequency card, dark-glass low-frequency card.
- Preserved hover lift, focus visibility, reduced-motion behavior, search, sorting, and detail navigation.

## Findings

- P0: None.
- P1: None.
- P2: None.
- P3: Theme trace intensity can be tuned later per body area without changing the shared hierarchy.

final result: passed

---

# Design QA — Training background, Tools, and Silent Health

- Source visual truth: `web_desktop/frontend/assets/training-archive-collage-v2.png`
- Full-view implementation: `C:\Users\26087\.codex\visualizations\2026\07\16\fitness-ledger-tools-training-qa\training-overview.png`
- Tools implementation: `C:\Users\26087\.codex\visualizations\2026\07\16\fitness-ledger-tools-training-qa\tools-overview.png`
- Needs-review state: `C:\Users\26087\.codex\visualizations\2026\07\16\fitness-ledger-tools-training-qa\training-needs-review.png`
- Data Health overlay: `C:\Users\26087\.codex\visualizations\2026\07\16\fitness-ledger-tools-training-qa\data-health-overlay.png`
- Combined comparison evidence: `C:\Users\26087\.codex\visualizations\2026\07\16\fitness-ledger-tools-training-qa\training-comparison.png`
- Viewports: 1920 × 1080 and 1440 × 900
- State: anonymous archive fixture; Training overview; Tools overview; separate `NEEDS_REVIEW` fixture with 3 issues

## Findings

- No actionable P0/P1/P2 findings remain.
- Fonts and typography: the existing editorial serif and DM Sans hierarchy is preserved. The generated background contains no embedded text and does not interfere with display typography or small UI labels.
- Spacing and layout rhythm: Training keeps its established archive measure. Tools now uses the full 1220px content measure with one continuous workbench, a stable dark ledger rail, and three horizontally readable action rows.
- Colors and visual tokens: the generated warm-paper, graphite, muted blue, teal, and ochre palette remains within the existing archive language. The Data prompt uses the existing restrained warm-yellow semantic accent.
- Image quality and asset fidelity: the selected 1536 × 1024 generated raster is used directly. Its equipment details remain visible at both desktop viewports while the center corridor stays quiet enough for the Training UI.
- Copy and content: Tools explains Export, Sync, and Data Health without inventing new capabilities. The nav prompt is labelled `Data` and appears only with a real positive issue count.

## Focused-region evidence

- `training-needs-review.png` confirms the quiet `Data 3` prompt sits beside `LOCAL-FIRST / PRIVATE`, outside primary navigation.
- `data-health-overlay.png` confirms the prompt's destination remains the contextual overlay rather than a full-page route.
- `tools-export.png` and `tools-sync.png` confirm the existing Export and Cloud Sync surfaces still render through the consolidated Tools route.

## Comparison history

1. Initial browser pass found a P1 Tools width regression: `.tools-page` combined `max-width:1220px` with global page padding, leaving only about 500px for content. Evidence was the first `tools-overview.png` capture.
2. Fixed by removing the outer max-width constraint and applying an explicit 1220px archive content measure through page padding. The revised 1920px and 1440px captures show the workbench spanning the intended width with readable action rows.
3. Post-fix Training comparison confirms the selected background remains edge-weighted, visible, and subordinate to content. No further P0/P1/P2 issues were found.

## Browser and interaction verification

- Headless Microsoft Edge rendered Training, Tools, Export, Sync, and Data Health at the target desktop viewports.
- The Silent Health browser harness verified issue prompt visibility, overlay opening, acknowledgement refresh, overlay closing, and URL preservation.
- Clean, zero-issue, loading, and unavailable states keep the top navigation silent.
- JavaScript syntax and the relevant regression suites completed without uncaught page-script failures.
- No real CloudBase upload or formal-data write was executed.

## Follow-up polish

- P3 only: the exact background visibility can be tuned after subjective review without changing the asset or layout.

final result: passed
