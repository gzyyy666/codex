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
- Group panels are visually heavier than the page without becoming full-color poster blocks.
- Black, warm yellow, paper gray, and graphite are the dominant materials; body-area colors appear as restrained edge and trajectory accents.
- The approved body-area illustration is cropped at the panel edge, monochrome, and visible on second inspection.

## Focused region comparison

- Back and shoulder panels were reviewed at original screenshot resolution.
- Lead cards are larger, warmer, and more elevated than medium- and low-frequency cards.
- Medium-frequency paper-gray cards retain transparency so the panel and colored trajectory traces remain visible.
- Low-frequency graphite cards remain readable and do not resemble disabled controls.
- Chinese names, English subtitles, session counts, and `Open trajectory` remain clear over every surface.

## Required fidelity surfaces

- Typography: unchanged editorial hierarchy; movement labels retain readable optical weight and truncation behavior.
- Spacing: existing compact archive matrix and two-column rhythm preserved.
- Colors: global cream/graphite/yellow palette restored; five body-area colors restricted to accents and traces.
- Image quality: existing approved local body-area artwork retained; no placeholder or code-drawn illustration introduced.
- Copy: no copy or data behavior changed.

## Patches made

- Replaced large body-area color fills with weighted neutral graphite panel gradients.
- Added theme-colored header anchors, panel trajectory traces, card edge accents, and numbering.
- Changed artwork to a cropped monochrome semantic layer with controlled visibility.
- Established three card levels: yellow lead card, translucent gray medium-frequency card, graphite low-frequency card.
- Preserved hover lift, focus visibility, reduced-motion behavior, search, sorting, and detail navigation.

## Findings

- P0: None.
- P1: None.
- P2: None.
- P3: Theme trace intensity can be tuned later per body area without changing the shared hierarchy.

final result: passed
