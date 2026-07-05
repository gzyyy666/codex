# Reusable Workflow Lessons

## Engineering

1. Build one authoritative write boundary. Desktop and Web now share `LedgerCommandService`; UI code never owns JSON safety.
2. Keep raw input immutable. Structured fields may be corrected, mapped, renamed, or deleted while raw text remains available.
3. Use stable movement IDs. Display names and aliases change; history identity must not.
4. Treat duplicate dates as an explicit decision: overwrite, append training, or cancel.
5. Use atomic temporary-file replacement and paired checkpoints for tracker and dictionary changes.
6. Prefer small request routing indexes over repeatedly scanning a large monolithic desktop file.

## Web Interaction

1. Visual affordance must match the actual click target. Named detail actions own navigation; entire cards remain inert unless explicitly designed otherwise.
2. Event delegation selectors must target controls, not ancestor state containers. The Training root also carries `data-training-theme`; using a broad ancestor selector caused search controls to rerender the page on click.
3. Preserve search and ordering state across in-page rerenders.
4. Search semantics must match user intent. Training overview searches daily split/date; selected body archives include days by split, then show only relevant movements and movement notes.
5. Support real mouse, keyboard, focus-visible, reduced-motion, and common date formats.

## Product Design

1. Start with one visual protagonist per screen, then subordinate status and metadata.
2. Editorial quality comes from hierarchy, density contrast, and composition, not from adding cards everywhere.
3. Material depth uses contact shadow, ambient shadow, inner highlights, and restrained lift. Avoid black heavy shadows, neon, and game-like 3D.
4. Dense information pages need designed objects, not spreadsheet grids: slips, receipts, archive boards, trajectories, and compact control rails.
5. Decorative imagery must support body-area or archive meaning and must never push primary data below the fold.
6. Keep a project-specific Style Bible. Generic design references are secondary and cannot override established product identity.
7. Validate visual work in the real browser at multiple widths; generated mockups are direction, not proof of implementation.

## Collaboration And Memory

1. Store durable facts, decisions, and workflows; do not store raw conversations.
2. Keep one canonical local clone of the memory repository.
3. Create Git checkpoints only after verification, not after every experiment.
4. Replace piles of screenshots with a small set of final evidence images and a written design system.
5. When context is confused, recover from repository indexes and confirmed rules instead of repairing assumptions from chat compression.
