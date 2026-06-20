---
id: vocab-studio-state-20260620
type: memory
status: active
updated: 2026-06-20
tags: [vocab-studio, desktop-tool, python, tkinter, rollback]
source: local snapshot 20260620_214933
---

# Vocab Studio State Snapshot

## Summary

Vocab Studio is the user's local Windows desktop vocabulary trainer, maintained as a Python/Tkinter app. The current stable rollback point was captured on 2026-06-20 at local timestamp `20260620_214933`.

## Current Location

```text
C:\Users\26087\Documents\Codex\2026-06-16\vs-code-ai\work\vocab_trainer
```

Current main program:

```text
stable_app.pyw
```

Current desktop launcher:

```text
C:\Users\26087\Desktop\Vocab Studio.lnk
```

Project-specific maintenance rule:

```text
C:\Users\26087\Documents\Codex\2026-06-16\vs-code-ai\work\vocab_trainer\VOCAB_STUDIO_MAINTENANCE.md
```

## Local Backup

Rollback backup created:

```text
C:\Users\26087\Documents\Codex\2026-06-16\vs-code-ai\work\vocab_trainer\backups\vocab_studio_snapshot_20260620_214933
C:\Users\26087\Documents\Codex\2026-06-16\vs-code-ai\work\vocab_trainer\backups\vocab_studio_snapshot_20260620_214933.zip
```

The backup includes the app files, `data/`, `VOCAB_STUDIO_MAINTENANCE.md`, and a copy of `Vocab Studio.lnk`.

## Functional State To Preserve

- Batch import from pasted text grouped by date.
- Date markers such as `6.16`, `6/16`, and full dates.
- Word splitting by newline, slash, comma, semicolon, Chinese punctuation, tabs, and two-plus spaces.
- Phrase preservation for single-space phrases such as `have sb over` and `hanging by a thread`.
- Meaning lookup uses `lookup_cache.json` first, then online translation.
- No local hard-coded fallback dictionary should be reintroduced unless explicitly requested.
- Official vocabulary data lives in `data/vocabulary.json`.
- Translation cache lives in `data/lookup_cache.json`.
- Settings live in `data/config.json`.
- Windows local TTS is used at runtime; no audio library is stored.
- Library table is sorted newest first.
- Review modes are `Review 10`, `Listen -> Meaning`, and `Meaning -> Spell`.
- Review uses weighted selection based on age, wrong count, and mastery.
- Review is self-graded with `I was right` / `I was wrong`.

## Recovery Instructions

If the app breaks, close Vocab Studio, restore the backup zip into the app folder, and ensure `stable_app.pyw` plus `data/` are restored.

If the desktop shortcut breaks, restore the copied `Vocab Studio.lnk` from the backup to:

```text
C:\Users\26087\Desktop\Vocab Studio.lnk
```

If Codex memory becomes confused, instruct Codex to read this node and:

```text
C:\Users\26087\Documents\Codex\2026-06-16\vs-code-ai\work\vocab_trainer\VOCAB_STUDIO_MAINTENANCE.md
```

Then ask it to restore its Vocab Studio understanding to this state before making changes.

## Review

- Next review: 2026-07-20
- Archive when this snapshot is superseded by a newer stable backup.
