"""Deterministic note scope parsing and semantic normalization.

This module is intentionally UI/parser agnostic.  It owns the one text
normalization rule used by the command boundary, projections, and exports.
"""

from __future__ import annotations

import re
from textwrap import dedent


_NOTE_LABELS = (
    ("diet_notes", re.compile(r"^(?:diet\s+notes|饮食备注)\s*[:：]\s*(.*)$", re.I)),
    ("training_notes", re.compile(r"^(?:training\s+notes|训练备注)\s*[:：]\s*(.*)$", re.I)),
    ("daily_notes", re.compile(r"^(?:notes?|备注)\s*[:：]\s*(.*)$", re.I)),
)

# These are the maintained section labels.  Numeric fields are handled by a
# separate value-aware matcher below so prose such as "calories are high"
# does not terminate a Notes block.
_SECTION_LABELS = re.compile(
    r"^(?:training|训练|训练部位|training\s+(?:part|split)|cardio|有氧|diet|饮食|"
    r"notes?|备注|diet\s+notes|饮食备注|training\s+notes|训练备注)\s*[:：]",
    re.I,
)
_NUMERIC_FIELD_LABELS = re.compile(
    r"^(?:weight|体重|body\s+fat|体脂(?:率)?|waist|腰围|sleep|睡眠|steps?|步数|"
    r"calories?|kcal|热量|卡路里|protein|蛋白质|carbs?|carbohydrate|碳水(?:化合物)?|"
    r"fat|脂肪)\s*[:：]\s*[-+]?\d+(?:\.\d+)?\s*$",
    re.I,
)
_BOWEL_FIELD_LABELS = re.compile(
    r"^(?:bowel(?:\s+movement)?|排便)\s*[:：]\s*\S.*$",
    re.I,
)


def is_structural_boundary(line: str) -> bool:
    """Return whether an unindented line starts a maintained structure.

    This is the single boundary predicate shared by top-level Notes parsing
    and training-section extraction.  It intentionally requires numeric
    values for numeric fields, keeping natural-language prose in Notes.
    """

    text = str(line or "").rstrip()
    if not text or text[0].isspace():
        return False
    return bool(
        _SECTION_LABELS.match(text)
        or _NUMERIC_FIELD_LABELS.match(text)
        or _BOWEL_FIELD_LABELS.match(text)
    )


def normalize_note_text(value: str | None) -> str:
    """Normalize representation noise while preserving meaningful prose.

    CRLF/LF, trailing line spaces, and note-block boundary whitespace are not
    business changes.  Internal blank lines, punctuation, ordering, and user
    wording are retained exactly.
    """

    if value in (None, ""):
        return ""
    lines = str(value).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = [line.rstrip() for line in lines]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if lines:
        lines[0] = lines[0].lstrip()
        lines[-1] = lines[-1].rstrip()
    return "\n".join(lines)


def _clean_block(lines: list[str]) -> str:
    # Canonical note content may be visually indented one structural space.
    # Dedent only a common indentation; do not strip meaningful internal text.
    return normalize_note_text(dedent("\n".join(lines)))


def extract_note_sections(raw: str) -> dict[str, str]:
    """Extract only explicit top-level daily/diet/training note sections."""

    result = {"daily_notes": "", "diet_notes": "", "training_notes": ""}
    current: str | None = None
    in_training = False
    raw_lines = str(raw or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: dict[str, list[str]] = {key: [] for key in result}
    for index, raw_line in enumerate(raw_lines):
        line = raw_line.rstrip()
        is_top_level = bool(line) and not line[0].isspace()
        matched = None
        if is_top_level:
            for scope, pattern in _NOTE_LABELS:
                match = pattern.match(line)
                if match:
                    matched = (scope, match.group(1))
                    break
        if matched:
            if matched[0] == "daily_notes" and in_training:
                next_line = raw_lines[index + 1].strip() if index + 1 < len(raw_lines) else ""
                # Historical input sometimes used an unindented action note.
                # Keep that compatibility only when the next line clearly
                # starts another action; otherwise this is the Daily scope.
                if re.match(r"^\d+\s*[.)、。]", next_line):
                    current = None
                    continue
                in_training = False
            current = matched[0]
            if matched[1]:
                blocks[current].append(matched[1])
            continue
        if is_top_level and is_structural_boundary(line):
            if re.match(r"^(?:training|训练)\s*[:：]", line, re.I):
                in_training = True
            elif re.match(r"^(?:diet|饮食|cardio|有氧|training\s+notes|训练备注|diet\s+notes|饮食备注)\s*[:：]", line, re.I):
                in_training = False
            current = None
            continue
        if current is not None:
            blocks[current].append(line)
    for scope, lines in blocks.items():
        result[scope] = _clean_block(lines)
    return result


def normalize_action_note_block(value: str | None) -> str:
    """Remove the one structural action indentation before saving an instance note."""

    return _clean_block(str(value or "").split("\n"))
