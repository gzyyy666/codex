# Mobile UI And State Model

The mobile viewer translates the Web identity rather than copying its wide layout.

- Single-column warm paper surface
- Graphite text and restrained Volt action
- Compact archive cards and readable tabular data
- Persistent read-only label and sync timestamp
- Collapsed long Chinese notes
- Large touch targets and shallow navigation
- Training Reference has a neutral local-only freeform TRAINING NOTE with an
  inline Archive editor and a scroll-revealed collapsible Dock. Both editors
  share one Storage key; the Dock must never be treated as a formal training
  record or CloudBase write surface.
- Movement candidates are a separate neutral overlay above the reference flow.
  Visible, loading, empty, history-error, internally-scrolling, and collapsed
  states all leave the note editor usable. The initial viewport favors one
  latest session; older sessions remain inside the overlay's scroll area.

Pages: Home, Today, Training Reference, Search, Movement Detail, Record Detail, and Data Status.

Every data page handles loading, empty, error, unauthorized, unconfigured, and successful states. `fl_meta.generated_at` is the freshness authority. The UI should warn when it exceeds `staleAfterHours`; this can be enabled during real CloudBase integration.
