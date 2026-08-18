# Fitness Ledger Web Style Bible

Version: 2026-08-10 / current formal baseline

This is the visual and interaction authority for future Fitness Ledger Web
work. It is intentionally concrete: a new screen should feel like it belongs
to the existing product before it introduces any new visual idea.

## Evidence and authority

The current baseline was captured from the formal application using anonymous
review fixtures at a 1600 x 1000 viewport. Accepted evidence is in:

- `docs/design/evidence/2026-08-10/00-home.png`
- `docs/design/evidence/2026-08-10/01-body.png`
- `docs/design/evidence/2026-08-10/02-diet.png`
- `docs/design/evidence/2026-08-10/03-training.png`
- `docs/design/evidence/2026-08-10/04-movements.png`
- `docs/design/evidence/2026-08-10/05-tools-export.png`

The evidence is visual grounding only; it contains no personal records. The
live implementation remains the final authority for behavior and data.

## Product character

Fitness Ledger is a private local fitness journal with an editorial archive
surface. It should feel tactile, quiet, deliberate, and data-honest:

- warm paper and graphite form the stable base;
- large editorial typography establishes page identity;
- real fitness imagery is atmospheric, never a substitute for data;
- paper slips, receipts, hairlines, contact shadows, and translucent layers
  create physical depth;
- amber/gold is reserved for action and focused body themes;
- mint signals local-first safety or a verified state;
- the interface should remain fast and readable while the visual surface feels
  composed rather than utilitarian.

Do not turn the product into a generic dashboard, a neon fitness game, a dense
spreadsheet, a black admin console, or a card grid where every card has the same
material identity.

## Global tokens

These values are taken from the current Web stylesheets. Reuse the tokens or
their semantic equivalents instead of inventing nearby values.

### Color

| Role | Value | Use |
| --- | --- | --- |
| paper | `#f8f5ed` | page canvas and light paper |
| paper deep | `#f2ede2` | warm recesses |
| paper light | `#fcf9f2` | clean foreground paper |
| ink | `#000` | display titles, primary text, active nav |
| graphite | `#707070` | secondary copy and quiet metadata |
| graphite dark | `#28251f` | material text and dark surfaces |
| volt / sun | `#ffda6e` | primary action, selected control, warm cue |
| brass | `#b88924` | restrained theme accent |
| mint | `#6ece9d` | local-first and verified status |
| danger | `#bd3f35` | errors only |

Body-area themes are stable semantic colors, not interchangeable decoration:

| Theme | Accent | Soft tint | Meaning |
| --- | --- | --- | --- |
| shoulders | `#d49a27` | `#f2d88b` | lift / amber |
| chest | `#c86454` | `#efb9ae` | coral / expansion |
| back | `#34776f` | `#afd6cc` | teal / structure |
| legs | `#8065a8` | `#d5c5e8` | violet / grounding |
| arms | `#3f86a2` | `#b8dce8` | blue / rhythm |

### Typography

- UI and body: `DM Sans`, then `Microsoft YaHei UI`, then a sans-serif fallback.
- Editorial display: `Iowan Old Style`, `Palatino Linotype`, `Georgia`, serif.
- Display titles are large, high-contrast, and tightly tracked; do not replace
  them with a geometric sans.
- Eyebrows and section labels use compact uppercase text, generous tracking,
  and low visual weight.
- Chinese copy must remain readable at normal scale; never use low-opacity
  decorative Chinese text as the only label.

### Geometry and spacing

- card radius: `24px`
- large panel radius: `30px`
- control radius: `12px`
- input radius: `6px`
- pill radius: `9999px`
- rhythm: `8 / 16 / 24 / 32 / 48 / 64px`
- wide page measure: `1500px`
- wide page gutter: `clamp(22px, 3vw, 56px)`

Rounded geometry has meaning. Use 6px for fields, 12px for compact controls,
24px for physical cards, 30px for large panels, and pills only for compact
status or navigation controls.

### Materials and shadows

Use a maximum of three visible layers:

1. archive image or quiet texture in the background;
2. paper, glass, or receipt content surface;
3. tactile foreground control or action.

Preferred surfaces:

```css
--surface-paper: linear-gradient(145deg, rgba(255,253,247,.96), rgba(244,238,227,.84));
--surface-paper-strong: linear-gradient(145deg, #fffdf7 0%, #f0e7d8 100%);
--surface-frosted: linear-gradient(145deg, rgba(255,253,247,.8), rgba(241,234,223,.62));
--surface-dark-panel: linear-gradient(145deg, #252621 0%, #10110e 100%);
```

Preferred depth:

```css
--shadow-contact: 0 1px 1px rgba(38,30,18,.09), 0 3px 5px rgba(38,30,18,.07);
--shadow-float: 0 2px 4px rgba(38,30,18,.08), 0 18px 46px rgba(45,35,20,.115);
--shadow-lift: 0 4px 7px rgba(38,30,18,.09), 0 27px 62px rgba(45,35,20,.145);
```

Every raised object needs a tight contact shadow and a larger, quieter ambient
shadow. Frosted surfaces always have a solid warm-paper fallback; blur must
never be the only source of contrast. Grain is allowed only at very low
opacity and must not interfere with Chinese text.

## Global shell

- Use one compact horizontal header on the Web desktop surface.
- The monogram sits in a small warm rounded square; the stacked wordmark reads
  `FITNESS / LEDGER` with the small line `MOVE. RECORD. KNOW.`.
- Navigation is text-first. The active route is a black pill with light text;
  inactive routes are quiet graphite text.
- The right side carries local-first, data, sync, and build identity as small
  badges. These never become a second action toolbar.
- The floating Guardian Pet may appear as a persistent utility layer. It must
  remain visually secondary to the page's records, controls, and primary action.
- Use visible focus rings and a restrained hover lift. Do not make the whole
  record card clickable when a named action already exists.

## Page recipes

### Home / Daily Capture

The home page is a cinematic entry, not a dashboard:

- a dark monochrome hero with a strong editorial title such as `Daily Capture`;
- Chinese explanatory copy underneath, never hidden in a tooltip;
- one amber primary action for writing today's log;
- one quiet archive link for movement history;
- a pale receipt at the upper right for the latest entry;
- a warm recent-archive strip below, with three readable slips and a small
  body-area utility illustration at the edge.

The hero image is `fitness-journal-hero.png`. Keep the image dark enough that
the title and copy read first. The latest receipt may overlap the image but must
not obscure the main action.

### Body Records

- Use the `Body Records` editorial heading and a short factual subtitle.
- Keep search, time range, and sort controls in one restrained toolbar.
- Let the 90-day field show real date positions and missing days; never invent
  continuity by compressing empty dates.
- Body slips may use violet, blue, or muted theme surfaces, but values and the
  explicit `Open record` action must remain readable.
- Use `body-archive-editorial-v2.png` as a quiet background illustration. It is
  an atmospheric layer, not a chart or a content card.

### Diet Records

- Use warm paper slips and prioritize date, calories, and macros.
- Keep full meal text in explicit detail rather than making every card a long
  paragraph.
- Search and newest/oldest ordering are enough for the primary archive toolbar.
- Do not add meal taxonomy filters unless the product model explicitly changes.
- Use `diet-archive-collage.png` as a subdued archive motif.

### Training Records

- The first screen is the `Training body map`, not a separate mode tab.
- Show five compact tactile theme cards: shoulders, chest, back, legs, arms.
- Each card displays live session/movement counts and representative imagery.
- `All records` is the overview state. Selecting a theme updates the same
  route, header, atmosphere, filtered records, card accents, and focus panel.
- The selected desktop state uses an archive composition: tall theme cover,
  factual receipt summary, search/sort controls, and compact chronological
  record slips.
- The summary may show only facts derived from records. Never invent 1RM,
  monthly trends, conclusions, or coaching advice.
- Mixed-theme days remain visible when included by their stored training theme,
  but the selected view narrows movement names and notes to the selected area.
- Keep cards searchable, sortable, and explicitly openable.
- Use `body-themes-v2/{shoulders,chest,back,legs,arms}.png` consistently.

### Movement Index

- Heading: `Movement Index`, a short Chinese explanation, search, result count,
  and a contextual `Manage Dictionary` entry.
- Organize by body-area group, not a spreadsheet grid and not oversized isolated
  tiles.
- Every group has a body-area color base, a recognizable representative image,
  a controlled veil, and translucent foreground movement tiles.
- The lead movement is a warmer, larger paper tile. Secondary movements remain
  legible but allow the group art to show through.
- Cards are the first read; art is semantic context, not a poster.
- The five body-area mapping must stay stable across Training and Movement.

### Movement Detail

- The chart and recent records are primary; the title/illustration is compact.
- Use sparse session nodes with a shared floor and honest labels. A single
  session is one recorded session, not a trend.
- Hover/focus exposes date, value, set count, and workload. Activation routes
  through the existing date plus `movement_id` navigation.
- Never connect missing sessions or manufacture a stronger trend.
- Provide a reduced-motion fallback and preserve keyboard access.

### Tools / Export

- Tools is a local maintenance workbench, not a generic settings dashboard.
- The opening read is a large Chinese question, a short explanation, and one
  clear path into the export operation.
- Use a warm paper control card beside a dark graphite export capsule.
- Natural language and JSON are an explicit toggle, not an icon-only control.
- The export CTA is the only high-weight action. Copy/download actions appear
  after a successful result.
- Diagnostics, hashes, provider details, and raw reports stay behind an
  Advanced/Recovery disclosure.
- State copy must distinguish local source data from a read-only CloudBase
  replica and must reassure that a failed sync cannot overwrite local data.

## Motion language

Motion communicates contact, connection, and state change:

- 160ms fast, 260ms normal, 420ms slow;
- ease-out interpolation and slight lift/pressed translation;
- shadow expansion on hover and compression on active;
- restrained staggered record reveal and theme interpolation;
- never particles, neon pulses, elastic bounce, large parallax, rotating 3D,
  or motion that delays daily use.

Always implement `prefers-reduced-motion: reduce` as a real behavior fallback.

## Responsive contract

- Wide desktop: preserve editorial title scale, the five-theme map, the
  factual summary, and the first record in the first screen.
- Around 1120px: collapse wide multi-column compositions without hiding the
  primary action or search/sort controls.
- Around 980px and 720px: stack panels and let controls wrap; maintain the same
  route and semantic order.
- Around 640px/560px: reduce title size and padding, keep touch targets large,
  and avoid preserving desktop whitespace.
- Check 1280px, 1440px, 1600px, current Windows DPI, Chinese clipping, long
  movement names, and keyboard focus.

## Future design-dialog contract

Before generating a new interface, the responsible conversation must:

1. Read this file, `docs/design/DESIGN_RESOURCES.md`, and
   `docs/design/AI_DESIGN_REVIEW_CONTRACT.md`.
2. Inspect the current route and the closest evidence screenshot.
3. Reuse existing tokens, body-area mapping, asset paths, and interaction
   semantics before proposing new ones.
4. State which page recipe is being extended and which material layer changes.
5. Preserve data truth, explicit actions, focus-visible states, reduced motion,
   and local-first copy.
6. Capture the changed route at the same viewport and compare it with the
   closest accepted evidence before handoff.

The output should feel like an extension of Fitness Ledger, not a new design
system placed beside it.
