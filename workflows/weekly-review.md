# Weekly Review Workflow

Use when the user requests a review; weekly is a suggested cadence, not an
installed schedule. Produce proposed memory/action updates by default. Apply
memory changes or publish GitHub Issues only when explicitly requested and
through the applicable write mechanism; do not change stored memories merely
because they were reviewed.

## Inputs

- Recent chat summaries
- GitHub Issues and PRs
- Local notes
- Unfinished ideas
- Completed decisions

## Steps

1. Collect notes from the week.
2. Identify durable information:
   - repeated preferences
   - project facts likely to matter later
   - decisions with future consequences
   - reusable procedures
3. Propose corrections to existing memory nodes before proposing new ones.
4. Draft ADRs for decisions with lasting consequences when useful.
5. Draft independently reviewable action items; publish Issues only if requested.
6. Identify outdated memory with evidence; actual archival requires authorized
   memory maintenance rather than a routine file rewrite.

## Output

Create or update:

- `memory/*.md`
- `decisions/*.md`
- GitHub Issues, if the repository is connected

