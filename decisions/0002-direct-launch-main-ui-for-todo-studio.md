# 0002 Direct Launch Main UI For Todo Studio

Date: 2026-06-17

Status: Accepted

## Context

The Todo Studio desktop tool initially included an intermediate launcher with multiple choices. That added friction and kept extra windows around, while the intended user experience was a direct desktop click into the working task manager.

## Decision

Make the desktop shortcut open the main Tkinter task manager window directly. Keep the launcher only as a compatibility entry point, not as the default user-facing path.

## Consequences

- The user gets a one-click path from the desktop to the task manager.
- The primary UI can focus on task management instead of launch choices.
- The launcher remains available for backward compatibility, but it is no longer the default route.
- Future desktop-tool work should favor single-window entry points unless a launcher is explicitly required.

## Links

- Related memory node: `memory/projects.md`
- Related memory node: `memory/preferences.md`
- Related workflow: `workflows/project-first-python-learning-and-tool-building.md`
