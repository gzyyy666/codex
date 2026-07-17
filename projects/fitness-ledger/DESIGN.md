# Fitness Ledger Web Design System

Status: Canonical Web UI reference
Last updated: 2026-07-17

This file is the concise project entry point for the current Web design language. The detailed rules live in [`docs/design/STYLE_BIBLE.md`](docs/design/STYLE_BIBLE.md). `web_desktop/frontend/styles.css`, `app.js`, local assets, and validated browser captures are the implementation evidence. Older Nike/Pirsch extraction notes are not project guidance.

## Product character

Fitness Ledger is a local-first personal fitness archive: a premium editorial fitness journal, not a SaaS dashboard, admin console, social feed, or developer tool. The interface should feel like a private paper archive with tactile depth, quiet utility, and high information readability.

The visual anchor is always the page's actual record or action:

- Home: cinematic archive stage and latest entry.
- Daily Entry: ruled writing surface and formal save/review flow.
- Body, Diet, Training: readable daily archive records.
- Movement Index: usage-weighted movement groups and explicit detail actions.
- Movement Progress: trajectory and comparison history.
- Tools: Export, Cloud Sync, Data Health, and low-frequency Custom Metrics utilities.

## Canonical palette

| Role | Token | Value | Use |
| --- | --- | --- | --- |
| Paper | `--color-paper` | `#f8f5ed` | Global canvas |
| Paper light | `--color-paper-light` | `#fcf9f2` | Writing and detail surfaces |
| Paper deep | `--color-paper-deep` | `#f2ede2` | Quiet section contrast |
| Paper lilac | `--color-paper-lilac` | `#f5f0f4` | Restrained tonal variation |
| Ink | `--color-ink` | `#000000` | Headings, decisive rules, active navigation |
| Graphite | `--color-graphite` | `#28251f` | Current material-layer text and structural metadata |
| Muted text | `--color-muted-text` | `#746f66` | Quiet explanatory copy and low-emphasis metadata |
| Volt | `--color-volt` | `#ffda6e` | One primary action or local-change emphasis |
| Mint | `--color-mint` | `#6ece9d` | Local/privacy/success status only |
| Danger | `--danger` | `#bd3f35` | Error or destructive warning |
| Amber | `--amber` | `#c68616` | Quiet warning emphasis |

Do not use pure white as the default canvas. Yellow is a highlighter, not a broad background. Green is a status signal, not a generic CTA. Body-area colors are semantic theme accents and must remain restrained beneath the data layer.

## Typography

- UI and dense records: local DM Sans, with Microsoft YaHei UI fallback for Chinese text.
- Editorial display: Iowan Old Style, Palatino Linotype, or Georgia.
- Display titles may be large and tightly tracked; record content stays compact and readable.
- Eyebrows and section labels use uppercase, 10–12px type with generous tracking.
- Dates, counts, and measurements use tabular lining numerals where available.
- Chinese body copy uses at least 1.5 line height and must not be forced into narrow columns.

## Layout and rhythm

- Base rhythm: 8px (`8, 16, 24, 32, 48, 64`).
- Normal page measure: `1200px`; wide archive measure: `1500px` with responsive outer gutters.
- Desktop archive pages should use available width without stretching reading-specific subcomponents.
- Alternate spacious stage areas with compact record areas.
- Prefer asymmetry, partial rules, edge bleeds, cropped imagery, and controlled overlap over centered dashboard grids.
- Do not wrap every section in the same rounded card.

## Material system

Paper surfaces use warm tint, an inner highlight, and restrained contact/ambient shadows. Glass surfaces always have a warm opaque fallback; blur is never the only contrast source. Use three functional layers where appropriate:

1. low-contrast local archive imagery or page wash;
2. paper/glass content surfaces;
3. tactile controls and explicit actions in the foreground.

Use 6px inputs, 12px images, 24px archive cards, asymmetric archive shapes, and pills only for compact controls. Hover is a slight lift and shadow expansion; active is pressed translation and shadow compression. Respect `prefers-reduced-motion`.

## Page-specific rules

### Training

Training Records keeps its body-area theme controls on the first screen. Selecting a theme changes the existing page in place, not the route. The five approved local body-area illustrations remain semantic background layers beneath translucent theme cards and record surfaces. Training background collage may extend across the full page, but the center reading layer stays clean.

### Movement Index and Progress

Movement groups are ordered by use frequency and use one representative local illustration per body area. Cards remain the first read; imagery never covers names, counts, or actions. Movement Progress prioritizes the chart and recent trajectory over a decorative banner.

### Data Health

Tools → Data Health is the normal entry. The global navigation is silent for `OK`, zero issues, loading, and `UNAVAILABLE`. A positive `NEEDS_REVIEW` count may produce only a small edge hint that opens the contextual overlay. Closing it preserves the original page and URL.

### Cloud Sync

Cloud Sync is a local-first maintenance console. Its first read is the natural-language sync conclusion and one high-weight action. It must clearly distinguish manual triggering from background auto-sync, state that CloudBase is a read-only replica, and keep hashes, logs, SDK data, and raw reports inside Advanced / Recovery.

### Tools and Custom Metrics

Tools is a wide editorial utility workbench, not a management dashboard. Export, Sync, and Data Health remain explicit sections. Custom Metrics is a low-frequency management area that consumes generic Core definitions, projections, and Commands. It must not introduce metric-name-specific components or free-positioned widgets.

## Interaction rules

- Every visual action must be genuinely interactive and have visible focus feedback.
- Named detail actions are the only detail triggers; static record surfaces are not hidden links.
- Search, filters, sorting, navigation history, and overlays must perform real behavior.
- Read-only Web actions must say when formal editing belongs to the stable desktop app.
- Preserve local-first safety boundaries: Web UI does not directly write tracker JSON, expose secrets, alter CloudBase, or modify Mini Program behavior.

## Do not

- Do not turn the Web into a traditional SaaS dashboard or dense admin table.
- Do not introduce remote images, gradients, neon effects, particles, or decorative motion.
- Do not replace editorial serif display hierarchy with a generic dashboard font stack.
- Do not hide real errors, dates, or data-health state for visual consistency.
- Do not change data schemas or business semantics to satisfy a visual treatment.

## Validation baseline

Review at 1280px and 1440px desktop widths, including long Chinese labels, dates, actions, overlays, and scroll continuity. Check reduced motion, focus-visible states, and local asset loading. Update this file and the Style Bible whenever a durable visual token, page pattern, image rule, or interaction semantic changes.
