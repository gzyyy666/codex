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

# Design QA - Tools v6 Gentelella template adapter

Date: 2026-08-04

## Evidence

- Template visual source: `https://gentelella.colorlib.com/`
- Template architecture reference: `https://gentelella.colorlib.com/docs/architecture/`
- Template source capture: `C:\Users\26087\.codex\visualizations\2026\08\04\019fcbd3-65f2-7242-a598-121bb22af36c\gentelella-reference.png`
- Tools overview implementation: `C:\Users\26087\.codex\visualizations\2026\08\04\019fcbd3-65f2-7242-a598-121bb22af36c\tools-template-overview-final.png`
- Cloud Sync implementation: `C:\Users\26087\.codex\visualizations\2026\08\04\019fcbd3-65f2-7242-a598-121bb22af36c\tools-template-sync-final.png`
- Data Check implementation: `C:\Users\26087\.codex\visualizations\2026\08\04\019fcbd3-65f2-7242-a598-121bb22af36c\tools-template-health-final.png`
- Mobile implementation: `C:\Users\26087\.codex\visualizations\2026\08\04\019fcbd3-65f2-7242-a598-121bb22af36c\tools-template-mobile-v2.png`
- Desktop viewport: 1600 x 1000; interaction recheck: 1440 x 900
- Mobile viewport: 512 x 690 CSS px
- State: Tools overview; Cloud Sync not configured; Data Check archive clear with 0 unresolved and 5 acknowledged

## Template comparison

- The implementation follows the reference template's admin anatomy: breadcrumb/page header, status badge, operation panels, route/status handoff, verification summary, and progressive disclosure for advanced diagnostics.
- Existing Fitness Ledger visual tokens remain the source of truth for paper, ink, editorial serif, DM Sans UI copy, mint, and volt accents. The template supplies structure and density; it does not introduce a second runtime or unrelated visual system.
- Export is one operation card. Archive Health is one focused card with two equal, explicit actions: Cloud Sync and Data Check. The two actions share the local archive context but do not share responsibilities.
- Data Check is now a full review-queue page. Cloud Sync is now a focused status/route page with only the necessary sync actions, verification summary, and an advanced diagnostic disclosure.

## Interaction and browser verification

- Route chain passed: Tools -> Data Check -> Cloud Sync -> Data Check -> Tools.
- Separate route behavior passed: Movement Dictionary reaches `#dictionary`; Export reaches `#tools?panel=export`.
- Desktop route snapshots reported `scrollWidth === clientWidth` at 1440 x 900.
- Mobile route snapshots reported `body.scrollWidth === body.clientWidth === 497` and `documentElement.scrollWidth === documentElement.clientWidth === 497` for overview, Data Check, and Cloud Sync.
- The active Tools navigation item is automatically scrolled into view on narrow screens.
- `tools/web_polish_ui_test.py` passed with `FITNESS_LEDGER_WEB_POLISH_UI_OK`.
- `node --check` passed for the changed app surface and existing CSS3D module; `tools-page.design.json` parsed successfully; `git diff --check` passed.
- No formal CloudBase upload or formal-data write was executed.

## Findings

- P0: None.
- P1: None.
- P2: None.
- P3: The adapter can be tuned further if a later review wants tighter copy localization or a different template page variant; the core hierarchy and routes are complete.

## Implementation scope

- Added a local `tools-template-adapter.css` layer and linked it from the existing frontend.
- Kept the existing API contracts, data-check table/actions, export route, dictionary route, and sync diagnostics.
- Removed the Tools overview's CSS3D panel mount for this template pass so the reference structure is readable without a decorative layer.
- Documented the Gentelella v4 MIT reference and local-adapter approach in `THIRD-PARTY-NOTICES.md`.

final result: passed

---

# Design QA - Tools v5 archive control surfaces

Date: 2026-08-04

## Evidence

- Source visual truth: `C:\Users\26087\AppData\Local\Temp\codex-clipboard-79a3f4b8-9183-4287-a2fc-d778083b8bee.png`
- Combined comparison input: `C:\Users\26087\.codex\visualizations\2026\08\04\tools-v5\qa-comparison.png`
- Implementation screenshot, desktop: `C:\Users\26087\.codex\visualizations\2026\08\04\tools-v5\tools-wide.png`
- Implementation screenshot, 1440px recheck: `C:\Users\26087\.codex\visualizations\2026\08\04\tools-v5\tools-initial-recheck-2.png`
- Cloud Sync screenshot: `C:\Users\26087\.codex\visualizations\2026\08\04\tools-v5\cloud-sync.png`
- Data Check screenshot: `C:\Users\26087\.codex\visualizations\2026\08\04\tools-v5\data-check.png`
- Mobile screenshots: `C:\Users\26087\.codex\visualizations\2026\08\04\tools-v5\tools-mobile.png`, `cloud-sync-mobile.png`, `data-check-mobile.png`
- Desktop viewport: 1743 x 979; implementation pixels match source pixels at 1743 x 979; device scale factor 1; no density normalization required.
- Secondary desktop viewport: 1440 x 1200; mobile verification viewport reported by browser: 512 x 690 CSS px; no document horizontal overflow in either run.
- State: Tools overview first frame, Cloud Sync not configured, Data Check archive clear, existing Export route, separate Movement Dictionary route.

## Full-view comparison

- The implementation preserves the project's paper / ink / mint / volt language, editorial serif hierarchy, local-first status, and archive contour field.
- The prior three-card control arrangement is intentionally restructured: Export remains a separate operation; Archive Health owns Cloud Sync and Data Check; Movement Dictionary is a separate reference entry. This is an information-architecture change requested by the current design direction, not an accidental pixel drift.
- The workbench now reads as one archive field with two real operation surfaces. The shared route line and pointer light connect those surfaces without introducing a detached 3D model.

## Focused-region comparison

- Upper field: source rail and route map are visible only when the desktop canvas has enough side space; at 1440px they are hidden to prevent overlap or clipping. The 1440px recheck shows the title, description, and state strip are cleanly separated.
- Workbench: the Export surface retains the existing dark export affordance; Archive Health uses a light paper surface, a status pill, a Local -> Payload -> CloudBase route, and explicit Sync / Data Check actions.
- Secondary surfaces: Cloud Sync leads with configuration/status, then preserves the existing diagnostic data; Data Check leads with scan result, route state, summary metrics, and the existing issue table/actions.

## Required fidelity surfaces

- Typography: existing editorial font stack and DM Sans UI text remain in use; new copy is compact and action-led rather than adding an oversized campaign headline.
- Spacing and layout: the desktop workbench is asymmetrical but aligned; the side rails no longer clip at 1440px; mobile stacks the operation surfaces and keeps the workbench inside the viewport.
- Colors and visual tokens: no new dominant hue was introduced; state accents map to existing mint / volt semantics and the surfaces stay on the paper canvas.
- Image quality and asset fidelity: no new raster or illustration was introduced. Existing monogram, ghost companion, and export artwork remain local project assets; the 3D layer is DOM/CSS depth on the real controls.
- Copy and content: protocol behavior and data wording remain intact; the page now explains why Sync and Data Check share Archive Health while Dictionary stays separate.
- Icons: existing glyphs and local assets remain; no business action was replaced by a decorative CSS drawing.
- Accessibility and motion: real buttons retain keyboard focus styles; the pointer controller has bounded local tilt, resets on leaving the stage, and `prefers-reduced-motion` disables decorative motion.

## Interaction and browser verification

- Pointer test: moving over the upper hero leaves the lower Export card at `0.000deg`; moving onto the card produces bounded local tilt (`1.930deg` in the probe), confirming the first-frame tilt regression is fixed.
- Route test: clicking Open Cloud Sync reaches `#tools?panel=sync`; Data Check reaches `#tools?panel=health`; Export reaches `#tools?panel=export`; Movement Dictionary reaches `#dictionary`.
- DOM test: overview exposes only `export` and `sync` as tool cards; Data Check remains a subroute rather than a third peer card.
- Responsive test: desktop and mobile browser probes reported `scrollWidth === clientWidth`; no page-level horizontal overflow was observed.
- Console test: the initial pass found only the missing favicon 404; the existing monogram was registered as the favicon and the follow-up render produced no `Runtime.exceptionThrown` or `Log.entryAdded` events.

## Comparison history

1. Initial 1440px pass showed the decorative source rails clipped at the viewport edges. The source rail and route map were then hidden below 1600px and kept at a fixed outer offset only when the desktop canvas had enough side room.
2. The follow-up 1440px capture shows no rail clipping or hero overlap; the 1743px capture keeps the rails visible as intentional side structure.
3. The mobile pass found no page-level overflow; the existing header nav remains horizontally scrollable at narrow widths, while Tools content itself stacks.
4. After the favicon fix, the browser console pass was clean. No P0/P1/P2 findings remain.

## Open questions

- P3 only: after subjective review, the vertical reveal depth of the Archive Health surface can be tuned without changing its route, state model, or 3D architecture.

## Implementation checklist

- [x] Preserve existing Export and Movement Dictionary behavior.
- [x] Redesign Cloud Sync and Data Check presentation without changing their protocol semantics.
- [x] Keep 3D on the real DOM surfaces, not a separate model layer.
- [x] Verify first-frame pointer behavior, route transitions, responsive width, reduced motion, and console cleanliness.

final result: passed

## Follow-up correction — 2026-07-16

- Runtime diagnosis found two presentation issues: the preview service had exited, and the Training page still carried an older opaque parent background while the new atmosphere layer used an over-scaled `cover` crop.
- The parent `training-archive-collage.png` layer is now removed for the overview. The selected `training-archive-collage-v2.png` is the sole overview artwork, positioned above the page background and below content.
- The artwork now uses a smaller `86% auto` scale with vertical repetition so more equipment, calibration marks, and movement lines remain visible across the archive length.
- Final evidence: `C:\Users\26087\.codex\visualizations\2026\07\16\fitness-ledger-tools-training-qa\training-scaled-repeat.png` and `needs-review-final.png`.

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

---

# Design QA - Tools v7 three-source adaptation

Date: 2026-08-04

## Evidence

- Layout source: `https://collectiveos.vercel.app/`
- Motion source: `https://invisigrid.live/`
- Component source: `https://reactbits.dev/`
- Source captures: `C:\Users\26087\.codex\visualizations\2026\08\04\019fcbd3-65f2-7242-a598-121bb22af36c\references\collectiveos-1600-top.png`, `invisigrid-1600-top.png`, `reactbits-1600-top.png`, and their 390px captures
- Tools overview implementation: `C:\Users\26087\.codex\visualizations\2026\08\04\019fcbd3-65f2-7242-a598-121bb22af36c\tools-template-v7-final.png`
- Cloud Sync implementation: `C:\Users\26087\.codex\visualizations\2026\08\04\019fcbd3-65f2-7242-a598-121bb22af36c\tools-template-v7-sync-final.png`
- Data Check implementation: `C:\Users\26087\.codex\visualizations\2026\08\04\019fcbd3-65f2-7242-a598-121bb22af36c\tools-template-v7-health-final.png`
- Mobile implementation: `C:\Users\26087\.codex\visualizations\2026\08\04\019fcbd3-65f2-7242-a598-121bb22af36c\tools-template-v7-mobile.png`
- Viewports: 1600 x 1000 source/render capture, 1440 x 900 interaction recheck, 390 x 844 mobile
- State: Tools overview; archive clear; Cloud Sync not configured; Data Check remains a separate review queue

## Source-to-surface comparison

- Collective OS supplies the visible dashboard relationship: workspace rail, KPI strip, main operation area, and lower progressive sections. The source's copy, imagery, branding, and application code are not copied.
- Invisigrid supplies the motion rule: one quiet grid atmosphere, pointer-reactive light, and short scroll reveal. It does not become a second content layer or replace semantic controls.
- React Bits supplies the component behavior: Spotlight Card response on surfaces and Glare Hover feedback on action rows. These are local vanilla CSS/JS adaptations; no React runtime is added.
- Fitness Ledger relationships remain unchanged: Export is separate; Archive Health owns Cloud Sync and Data Check; Movement Dictionary remains a reference route.

## Interaction and browser verification

- Sidebar route chain passed: Overview -> Data Check -> Cloud Sync -> Data Check -> Overview.
- Separate sidebar routes passed: Movement Dictionary reaches `#dictionary`; Export reaches `#tools?panel=export`.
- Desktop snapshots reported `scrollWidth === clientWidth === 1425` at 1440 x 900.
- Mobile snapshot reported `body.scrollWidth === body.clientWidth === 375` and `documentElement.scrollWidth === documentElement.clientWidth === 375` at 390 x 844.
- The top Tools nav and the new workspace rail keep their active entries reachable on mobile; the rail itself scrolls without widening the page.
- Pointer and motion layers are bounded and removed from the reduced-motion path.
- `tools/web_polish_ui_test.py` passed with `FITNESS_LEDGER_WEB_POLISH_UI_OK`; app syntax and design JSON validation passed; `git diff --check` passed.
- No formal CloudBase upload or formal-data write was executed.

## Findings

- P0: None.
- P1: None.
- P2: None.
- P3: The reference motion can be tuned further after subjective review, but no structural or interaction defect remains.

final result: passed
