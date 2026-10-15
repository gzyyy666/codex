# Design Resources And Reproduction Guide

## Authority Order

1. `STYLE_BIBLE.md`: project-specific visual and interaction authority.
2. `evidence/`: final approved implementation screenshots.
3. `../../web_desktop/design_reference/`: imported tokens and reference analysis.
4. `../../DESIGN.md`: secondary external composition and interaction reference.

If references conflict, follow the Style Bible and current evidence.

## Current Design Name

**Tactile Editorial Fitness Archive**

Core characteristics:

- warm paper and ivory backgrounds
- graphite ink and restrained amber highlight
- editorial serif display hierarchy with quiet sans-serif metadata
- cinematic monochrome or abstract body imagery
- archive slips, receipts, writing slabs, body maps, and trajectories
- high information density without dashboard or spreadsheet styling
- foreground, midground, and background depth
- contact shadow plus ambient shadow, subtle edge highlight, and restrained glass
- low-amplitude lift, press, reveal, and theme transitions

## Frontend Files

- `web_desktop/frontend/styles.css`: historical and primary visual system.
- `web_desktop/frontend/final-pass.css`: final cascade for accepted archive layout and interaction fixes.
- `web_desktop/frontend/app.js`: HTML rendering, page state, search, sort, details, and API interaction.
- `web_desktop/frontend/assets/`: local offline imagery and fonts.

Prefer existing owned stylesheets and consolidate redundant overrides.
A genuinely separate component/surface may justify a bounded stylesheet with
explicit ownership and load order; do not create another global override file
merely to win specificity. Do not bundle broad CSS cleanup into a small fix.

## Approved Evidence

- `evidence/daily-entry.png`
- `evidence/body-records.png`
- `evidence/training-shoulder-focus.png`
- `evidence/movement-index.png`
- `evidence/analysis-export-success.png`

These images are evidence of hierarchy and material quality, not pixel-perfect fixed layouts.

## Design QA Checklist

Select affected items; this is not a mandatory full pass for every copy/CSS
edit. Expand viewport/state coverage for layout, navigation or motion changes.

- 1280 px and 1440/1600 px desktop widths
- Chinese line wrapping and clipping
- no fake buttons or hidden card navigation
- visible hover and focus states
- selected Training search and ordering remain interactive
- Movement Dictionary has a return path
- Movement Progress excludes disabled dictionary entries but retains their data
- reduced-motion fallback
- no network-hosted visual assets
