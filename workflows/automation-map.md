# Automation Map

Use this file to decide which recurring tasks should become reminders, monitors, or GitHub workflows.

## Good Automation Candidates

- Weekly review and memory cleanup
- Monthly project status summary
- Monitoring important repository changes
- Converting captured ideas into draft issues
- Checking whether stale memory nodes need review

## First Automations To Try

| Automation | Cadence | Output |
| --- | --- | --- |
| Weekly memory review | Weekly | Updated `memory/` and `decisions/` |
| Idea triage | As needed | Draft GitHub Issues |
| Project health check | Weekly | Open risks and next actions |

## Automation Safety Rules

- Keep human review before publishing or deleting.
- Never automate secret collection.
- Prefer draft artifacts before live external changes.
- Log what changed and why.

