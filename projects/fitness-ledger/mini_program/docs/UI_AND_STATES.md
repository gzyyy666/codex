# Mobile UI And State Model

The mobile viewer translates the Web identity rather than copying its wide layout.

- Single-column warm paper surface
- Graphite text and restrained Volt action
- Compact archive cards and readable tabular data
- Persistent read-only label and sync timestamp
- Collapsed long Chinese notes
- Large touch targets and shallow navigation

Pages: Home, Today, Training Reference, Search, Movement Detail, Record Detail, and Data Status.

Every data page handles loading, empty, error, unauthorized, unconfigured, and successful states. `fl_meta.generated_at` is the freshness authority. The UI should warn when it exceeds `staleAfterHours`; this can be enabled during real CloudBase integration.
