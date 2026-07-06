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
