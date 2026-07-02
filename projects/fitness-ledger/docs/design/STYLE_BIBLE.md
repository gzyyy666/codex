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
- Hairlines use low-opacity ink; avoid thick gray borders.
- Rounded geometry has different personalities: 6px inputs, 12px images, 24px cards, large asymmetric archive shapes, and pills only for compact controls.
- Hover: slight lift and shadow expansion. Active: pressed translation and shadow compression.
- Respect `prefers-reduced-motion`.

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

### Body

Body slips may use controlled high-saturation tones, but foreground contrast must always pass. Color is meaningful or rhythm-driven, never a blind repeating pattern.

### Diet

Cards prioritize date, calories, and macros. Full meal text appears only in explicit detail.

### Training

Cards show date, session index, split, movement summary, and a brief note. The explicit detail action is the only detail trigger.

### Movement Index

An archive wall grouped by body area and sorted by use frequency. High-frequency movements receive more visual weight. Avoid spreadsheet grids and oversized single tiles.

### Movement Detail

The progression chart and recent records are primary. The title/illustration banner is compact and auxiliary.

### Data Check

Only the Open control opens issue details. The row itself is not clickable. Problem descriptions are in Chinese and the final column must remain fully visible.

## 10. Interaction Semantics

- A visual action must be genuinely interactive.
- Do not attach hidden navigation to an entire record when a named action exists.
- Focus-visible states are mandatory.
- Search and filters must perform real filtering.
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

