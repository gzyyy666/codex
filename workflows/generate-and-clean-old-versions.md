# Generate And Clean Old Versions

Use when replacement or cleanup is part of the requested task. Creating an
artifact alone does not require a separate cleanup pass over the user's files.

## Goal

Keep the working set tidy by replacing superseded artifacts and removing old versions when they are no longer needed.

## Steps

1. Create or update the new artifact.
2. Verify the new version works before removing anything old.
3. Identify superseded versions:
   - older desktop shortcuts
   - outdated generated outputs
   - obsolete launcher files
   - redundant copies in output folders
4. Replace/remove only the clearly task-owned superseded output when cleanup
   is in scope. Preserve user-authored, referenced or uncertain versions and
   retain a rollback copy when replacement could lose useful work.
5. Update a workflow/decision only when this task changes it; memory writes
   require an explicit user request, not merely a useful lesson.
6. Record the cleanup in Git when the repository is under version control.

## Safety Rules

- Do not delete user data, secrets, or source history without explicit confirmation.
- Keep compatibility fallbacks only when they are intentionally maintained.
- Prefer replacing in place over keeping multiple parallel versions.

## When To Apply

- Desktop shortcuts
- Generated UI assets
- Packaged deliverables
- Exported PDFs, docs, or spreadsheets
- Any artifact that has a clear successor

