# Generate And Clean Old Versions

Use this workflow whenever Codex creates or replaces a durable artifact such as a desktop shortcut, generated file, packaged output, or exported document.

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
4. Remove the superseded version if it is safe and no longer needed.
5. Update memory nodes or decisions if the replacement changes a durable preference or workflow.
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

