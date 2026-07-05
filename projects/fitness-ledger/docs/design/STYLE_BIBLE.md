# Fitness Ledger Visual Style Bible

Status: Active

Last updated: 2026-07-02

## 1. Design Name

**The Disciplined Archive**

Fitness Ledger treats personal training data as a private editorial archive: part training notebook, part measurement slip, and part cinematic fitness journal. It should feel designed and tactile without becoming decorative, playful, or dashboard-like.

## 2. Core Character

- Local-first and private rather than social or competitive.
- Editorial rather than administrative.
- Tactile paper and physical slips rather than generic white cards.
- Dense when reading records, spacious when introducing a section.
- Strong but restrained: graphite, warm ivory, amber-yellow highlight, and small status colors.
- Fitness imagery is documentary or graphic-archive material, never glossy stock-app decoration.

## 3. Visual Hierarchy

Each screen should have one dominant anchor:

- Home: cinematic Hero and `Daily Capture`.
- Daily Entry: the writing surface.
- Body/Diet/Training: the archive records.
- Movement Index: movement groups ordered by usage.
- Movement Detail: progression chart and recent trajectory.
- Data Check: issue severity and explicit repair entry.

Secondary information must not compete with the anchor. Metadata uses smaller type, quieter color, and tabular numerals.

## 4. Color System

| Role | Token | Current value | Use |
| --- | --- | --- | --- |
| Paper | `--color-paper` | `#f8f5ed` | Main background |
| Paper light | `--color-paper-light` | `#fcf9f2` | Writing and detail surfaces |
| Paper deep | `--color-paper-deep` | `#f2ede2` | Section contrast |
| Ink | `--color-ink` | `#000000` | Primary text and decisive rules |
| Graphite | `--color-graphite` | `#707070` | Metadata and explanation |
| Volt amber | `--color-volt` | `#ffda6e` | One primary action or latest state |
| Mint | `--color-mint` | `#6ece9d` | Success/local status only |
| Lilac paper | `--color-paper-lilac` | `#f5f0f4` | Quiet tonal variation |

Rules:

- Do not use pure white as the default surface.
- Use yellow as a highlighter, not as broad decoration.
- Use green only for success, privacy, or positive change.
- High/medium/low issue colors must retain readable text contrast.

## 5. Typography

- UI and dense records: DM Sans with Microsoft YaHei UI fallback.
- Editorial display titles: Iowan Old Style / Palatino Linotype / Georgia.
- Display titles may be oversized and tightly tracked, but record content remains compact.
- Section labels are uppercase, 10-12px, with generous letter spacing.
- Dates and metrics use tabular lining numerals.
- Chinese body text uses at least 1.5 line height and must not be forced into narrow columns.

## 6. Spatial Rhythm

- Use an 8px base rhythm: 8, 16, 24, 32, 48, 64.
- Alternate spacious stage areas with compact record areas.
- Prefer asymmetry and controlled overlap over perfectly centered dashboard grids.
- Use partial rules, edge bleeds, cropped imagery, and section numbering to guide the eye.
- Avoid wrapping every section in the same rounded card.

## 7. Material And Depth

- Paper surfaces use a warm tint, subtle inner highlight, and low ambient shadow.
- Physical slips may use a contact shadow close to the surface plus a larger diffuse shadow.
- Contact shadows use two stages: a tight 1-5px grounding shadow and a wider low-opacity ambient shadow. Floating surfaces may increase the ambient stage, but must keep the contact stage visible.
- Paper grain is allowed only as a very low-opacity local texture layer. It must not reduce Chinese text contrast or become a decorative pattern.
- Hairlines use low-opacity ink; avoid thick gray borders.
- Rounded geometry has different personalities: 6px inputs, 12px images, 24px cards, large asymmetric archive shapes, and pills only for compact controls.
- Hover: slight lift and shadow expansion. Active: pressed translation and shadow compression.
- Frosted surfaces require a solid warm-paper fallback and both standard and WebKit backdrop filters; blur is never the only source of contrast.
- Respect `prefers-reduced-motion`.
- High-availability surfaces use three explicit layers: background archive imagery, paper/glass content surfaces, and tactile foreground controls.
- Every primary page should have one memorable dominant material object. Supporting surfaces must have distinct identities rather than repeating the same card treatment.
- Material roles are functional: writing areas are thick paper/notebook slabs, summaries are translucent receipts, recent items are archive slips, primary actions are soft physical controls, and status is a restrained glass layer.
- Light archive pages build depth with contact shadow, ambient shadow, translucency, overlap, and edge highlights. Do not insert a heavy black banner merely to create contrast.
- Training body-area controls belong directly on the Training Records first screen; do not add an extra mode tab before them.
- A selected body area changes the existing Training Records page in place. It must not navigate to a separate reference route.
- The selected theme may change restrained atmosphere, representative offline imagery, record accents, and the right-side focus panel while preserving search, sorting, record cards, and explicit detail actions.
- Export actions must always use visible text labels; icon-only export controls are not permitted.
- Export is a compact single-screen workbench on standard desktop viewports: a restrained editorial header, warm paper control card, and dominant graphite export capsule.
- The control card should read as paper/frosted material; the capsule should read as a dark sanded physical slab with warm reflected light, not a flat black rectangle.
- The gold Generate control is the page's only strong CTA and uses a subtle top highlight, contact shadow, and pressed compression. Material depth must never obscure the date controls or generated download actions.

## 8. Image Direction

- Home uses cinematic monochrome fitness photography with directional crop and vignette.
- Archive pages use low-opacity collage, receipt, anatomical, or training-document motifs.
- Movement groups use one representative illustration per body area, applied to the group rather than implying one exact exercise.
- Images remain local and offline. Do not use remote hotlinks.
- Illustrations support data hierarchy; they never cover core values or labels.

## 9. Page Patterns

### Home

Cinematic stage, one large title, one compact status slip, and a short recent archive strip.

### Daily Entry

The textarea is a journal page, not a default form. Ruled lines, caret baseline, line height, and placeholder must align.
The complete entry area is a floating writing workbench: notebook slab as the dominant object, Today as a summary receipt, Recent Saved as layered archive slips, and local save readiness as a small glass status layer.

### Parse And Review

Use the `Review Scroll` pattern: a narrow sticky chapter index, one continuous warm-paper review document, compact summary slip, editable ledger sections, inline movement decisions, and a fixed bottom action rail. A faint local archive illustration may sit behind the upper-right area but must remain below field contrast. The amber action is reserved for `Confirm & Save`.

### Body

Body slips may use controlled high-saturation tones, but foreground contrast must always pass. Color is meaningful or rhythm-driven, never a blind repeating pattern.
Body filtering stays intentionally small: free-text/date search, a recent-days range, and newest/oldest ordering. Training, bowel, and cardio filter controls do not belong in the primary archive toolbar.

### Diet

Cards prioritize date, calories, and macros. Full meal text appears only in explicit detail.
Diet uses free-text/date search plus newest/oldest ordering. Meal-category selectors are omitted because the archive is organized by day rather than by meal taxonomy.

### Training

Cards show date, session index, split, movement summary, and a brief note. The explicit detail action is the only detail trigger.
The first screen includes five tactile theme controls: shoulder, chest, back, legs, and arms. They are a core section rather than tabs or filter chips.
Selecting a body area keeps the user on Training Records and synchronizes the header, atmosphere, active control, filtered records, card accents, and focus panel. `All Records` returns to the overview.
The five controls use compact premium theme cards with live counts, representative imagery, and active expansion. They must not become a game skill tree, particle system, or black control banner.
- In a selected body-area state, the active control moves to the foreground and expands into the archive anchor. The other four controls remain readable, discoverable switching indexes rather than fading into disabled decoration.
- On wide desktop screens, the selected state uses a focused archive composition: a tall body-area cover at left, a factual receipt summary at upper right, and dense chronological record slips below it. This replaces blank filtered space with a deliberate editorial hierarchy.
- The receipt may show only facts derived from current records, such as session count, latest date, movement count, frequent movements, and recent notes. Do not invent 1RM, monthly trends, or training conclusions.
- Focused record slips should be compact enough for comparison, with a themed edge and restrained alternating paper offsets; they must remain searchable, sortable, and explicitly openable.
- The focused layout may reorganize the control grid, but it must preserve the record search, sort, filtered history, and right-side factual summary.
- Shoulder uses the abstract lifted-arm artwork; Arms uses the separate dynamic push/arm artwork. Training and Movement Progress must resolve these assets consistently.
- Entering Training from another primary navigation page resets the view to the all-records overview. In-page body-area switching does not change the route.
- Training search matches only the stored training theme/split and date. Movement names and movement dictionary categories must not pull an unrelated daily session into search results.
- Selected body-area archives follow the same theme/split rule. A chest-theme day containing a shoulder accessory movement does not become a shoulder-theme day.
- Once a day is included by its training theme, its focused card must narrow Key Movements and movement notes to the selected body area. Mixed-theme days remain visible, but unrelated movements and notes do not.
- On selected desktop views, the four alternate body-area controls form a compact vertical index beside the active cover so the factual summary and first records remain visible in the first screen.
- The selected-state header may retain representative artwork, but it must also carry the search, order, and overview controls. Decorative space must not push the factual summary or first record below the fold.

## 10. Motion Language

- Motion communicates contact, connection, and state change rather than spectacle.
- Use slight lift, compressed press, gentle shadow expansion, staggered record reveal, and restrained theme interpolation.
- Theme color should propagate through the active control, atmosphere, record edge, focus panel, and explicit detail action.
- Avoid particles, large parallax, neon pulses, elastic bounce, rotating 3D objects, or animation that delays daily use.

### Movement Index

An archive wall grouped by body area and sorted by use frequency. High-frequency movements receive more visual weight. Avoid spreadsheet grids and oversized single tiles.
Movement Dictionary administration is entered from a tactile contextual control in the Movement Index heading area, not from the global navigation.

### Movement Detail

The progression chart and recent records are primary. The title/illustration banner is compact and auxiliary.

### Data Check

Only the Open control opens issue details. The row itself is not clickable. Problem descriptions are in Chinese and the final column must remain fully visible.

## 10. Interaction Semantics

- A visual action must be genuinely interactive.
- Do not attach hidden navigation to an entire record when a named action exists.
- Explicit record links should expose a restrained hover/focus hit area, not remain visually indistinguishable from static underlined text.
- Focus-visible states are mandatory.
- Search and filters must perform real filtering.
- Training search and sort state must remain functional in both the overview and selected body-area archive.
- Movement Dictionary must provide an explicit route back to Movement Index.
- Read-only Web actions must say that formal editing belongs to the stable desktop app.

## 11. Desktop Tkinter Translation

The local desktop application should echo, not imitate, the Web design:

- Use the same graphite/ivory/amber palette.
- Preserve simple rectangular geometry suitable for Tkinter.
- Prefer clear hierarchy and responsive expansion over complex effects.
- Never force a fixed 1.0 Tk scaling on high-DPI displays.
- Content frames must expand with the maximized window.
- Scrollable Text, Canvas, and Treeview regions must respond to the mouse wheel.

## 12. QA Checklist

- Verify at 1280px, 1440px, and the current Windows DPI scale.
- Check Chinese clipping, date alignment, and long movement names.
- Confirm the Data Check Open column is fully visible.
- Confirm only explicit detail actions open details.
- Confirm leg, shoulder, chest, back, arms, and core groups use the correct representative image.
- Confirm Movement Detail chart is legible before the trajectory list.
- Confirm local desktop pages fill the available window and wheel scrolling works.

## 13. Maintenance Rule

Update this document whenever a durable token, page pattern, image rule, or interaction semantic changes. Do not add one-off visual experiments until they have been validated in the running UI.

## 14. WeChat Mini Program Translation

The Mini Program is a gym-side reference tool, not a compressed copy of the desktop Web app.

- Its primary flow is `body area -> movement signals -> full trajectory`.
- Home prioritizes the five body areas above weight, calories, sync status, or long daily prose.
- The bottom navigation is `Home / Training / Search / Status`; the daily record is a secondary route.
- A movement list card shows latest performance, previous performance, historical best, session count, and at most two lines of notes.
- Daily food, body notes, and training prose are collapsed by default and always expose an explicit expand or detail action.
- Body-area colors follow the Web themes: shoulder amber, chest coral, back teal, legs violet, arms cyan.
- Mobile surfaces use one dark archive stage, tactile body-area controls, compact paper slips, and restrained contact shadows. Do not repeat one generic white rounded card for every content type.
- Search results show a clean title, type, date, and short preview. Never expose concatenated search-index text or duplicated aliases as the primary result.
- Mobile layouts optimize one-handed scanning and comparison. They must not preserve desktop whitespace, wide columns, or paragraph-heavy cards.
- Mini Program Home keeps the hero compact enough to show the body-area control and at least one movement card in the first practical scroll region.
- Home shows the two highest-frequency movements for the selected area; the Training tab owns the complete list and frequency/recent/name sorting.
- Movement Detail separates the latest three sessions from older history and shows reps plus volume as secondary comparison signals.
- Body and Diet are secondary archives entered from Status. Body uses controlled high-energy color slips; Diet uses warm paper notes. Neither belongs in the bottom navigation.
