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
- Group panels are led by a cropped black-gray geometric body figure rather than a flat color field.
- Mustard, coral, blue-green, smoky violet, and gray-blue act as local underglow in the space around the figure and through card gaps.
- The approved body-area figure occupies roughly 60-75% of each panel and is legible before the theme color becomes the dominant impression.

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

- Built each panel from a body-area underglow plus a dominant cropped monochrome figure.
- Kept restrained dark structural bands and panel edge accents behind the cards.
- Raised artwork coverage and visibility so black-gray human geometry occupies the panel majority instead of reading as a faint watermark.
- Established three card levels: translucent yellow lead card, light-glass medium-frequency card, dark-glass low-frequency card.
- Preserved hover lift, focus visibility, reduced-motion behavior, search, sorting, and detail navigation.

## Findings

- P0: None.
- P1: None.
- P2: None.
- P3: Theme trace intensity can be tuned later per body area without changing the shared hierarchy.

final result: passed
