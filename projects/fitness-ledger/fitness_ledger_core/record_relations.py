"""Canonical relationships for the local Fitness Ledger JSON store.

The tracker remains JSON for compatibility.  Daily movement instances belong
to ``TrainingSession.movement_items``; ``movements[*].history`` is rebuilt as
a read-only compatibility projection for older tools and external scripts.
Cardio belongs to ``DailyRecord.Cardio`` and is never part of a movement item
or a training session.
"""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
import os
from datetime import datetime
from typing import Any

from .training_organization import normalize_training_organization


RELATION_SCHEMA_VERSION = "fitness-ledger-relations-v1"
MOVEMENT_ITEMS_SCHEMA_VERSION = "fitness-ledger-movement-items-v1"
_COMPATIBILITY_DIAGNOSTICS: list[dict[str, str]] = []


def _compatibility_event(kind: str) -> None:
    if os.environ.get("FITNESS_LEDGER_COMPAT_DIAGNOSTICS") != "1":
        return
    caller = inspect.stack()[2].function
    _COMPATIBILITY_DIAGNOSTICS.append({"kind": kind, "caller": caller})


def compatibility_diagnostics(*, reset: bool = False) -> list[dict[str, str]]:
    events = list(_COMPATIBILITY_DIAGNOSTICS)
    if reset:
        _COMPATIBILITY_DIAGNOSTICS.clear()
    return events


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def canonical_date(value: Any) -> str:
    return str(value or "")[:10]


def record_day_id(value: Any) -> str:
    day = canonical_date(value)
    return f"day:{day}" if day else ""


def _stable_id(prefix: str, value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{prefix}:{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def _rows(database: dict, key: str) -> list[dict]:
    value = database.get(key, [])
    return value if isinstance(value, list) else []


def _movement_rows(database: dict) -> list[dict]:
    value = database.get("movements", {})
    if isinstance(value, dict):
        return [item for item in value.values() if isinstance(item, dict)]
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _touch_entity(row: dict, fallback_created: str = "") -> bool:
    changed = False
    if not str(row.get("id", "")).strip():
        row["id"] = _stable_id("record", {key: value for key, value in row.items() if key not in {"updated_at", "revision"}})
        changed = True
    if not row.get("revision"):
        row["revision"] = 1
        changed = True
    if "updated_at" not in row:
        row["updated_at"] = str(row.get("created_at") or fallback_created or "")
        changed = True
    return changed


def _movement_item_from_history(history: dict, session: dict) -> dict:
    item = copy.deepcopy(history)
    item_id = str(item.get("movement_instance_id") or item.get("id") or _stable_id("movement-instance", history))
    item["movement_instance_id"] = item_id
    item["id"] = item_id
    item["training_session_id"] = str(session.get("id", ""))
    item["record_day_id"] = str(session.get("record_day_id") or record_day_id(session.get("Date")))
    item["movement_id"] = str(item.get("movement_id") or "").strip()
    item.setdefault("order", None)
    item.setdefault("sets", [])
    # Cardio is deliberately not copied into the canonical movement item.
    item.pop("cardio", None)
    item.setdefault("raw", "")
    item.setdefault("notes", "")
    item.setdefault("exclude_from_progress", False)
    item.setdefault("revision", 1)
    item.setdefault(
        "updated_at",
        str(item.get("date") or session.get("Date") or "")[:10] + "T00:00:00"
        if str(item.get("date") or session.get("Date") or "")[:10]
        else "",
    )
    return item


def _legacy_history(database: dict) -> list[dict]:
    _compatibility_event("legacy_history_read")
    rows = []
    for movement in _movement_rows(database):
        fallback_id = str(movement.get("movement_id") or "").strip()
        for history in movement.get("history", []) or []:
            if not isinstance(history, dict):
                continue
            item = copy.deepcopy(history)
            item.setdefault("movement_id", fallback_id)
            item.setdefault("display_name", str(movement.get("name") or "").strip())
            rows.append(item)
    return rows


def _session_candidates(sessions: list[dict], history: dict) -> list[dict]:
    target_date = canonical_date(history.get("date"))
    target_day = str(history.get("training_day", "")).strip()
    exact = [
        session for session in sessions
        if canonical_date(session.get("Date")) == target_date
        and target_day
        and str(session.get("No.", "")).strip() == target_day
    ]
    return exact or [session for session in sessions if canonical_date(session.get("Date")) == target_date]


def _cardio_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, dict):
        return str(value or "").strip()
    labels = {
        "duration_minutes": "duration_minutes",
        "incline": "incline",
        "speed": "speed",
        "heart_rate": "heart_rate",
    }
    return "; ".join(f"{labels.get(key, key)}={value[key]}" for key in labels if value.get(key) not in (None, ""))


def cardio_migration_preview(database: dict) -> dict:
    """Describe legacy Cardio ownership without writing any file."""
    by_date: dict[str, dict] = {}
    for row in _rows(database, "daily_records"):
        day = canonical_date(row.get("Date"))
        value = str(row.get("Cardio", "") or "").strip()
        if day and value:
            by_date.setdefault(day, {"daily_value": value, "legacy_values": []})
    for session in _rows(database, "training_sessions"):
        day = canonical_date(session.get("Date"))
        value = _cardio_text(session.get("Cardio"))
        if day and value:
            by_date.setdefault(day, {"daily_value": "", "legacy_values": []})["legacy_values"].append({
                "source": "TrainingSession.Cardio",
                "training_session_id": str(session.get("id", "")),
                "value": value,
            })
    if database.get("movement_items_schema_version") != MOVEMENT_ITEMS_SCHEMA_VERSION:
        _compatibility_event("legacy_cardio_read")
        for movement in _movement_rows(database):
            for history in movement.get("history", []) or []:
                day = canonical_date(history.get("date"))
                value = _cardio_text(history.get("cardio"))
                if day and value:
                    by_date.setdefault(day, {"daily_value": "", "legacy_values": []})["legacy_values"].append({
                        "source": "tracker.movements[*].history[*].cardio",
                        "movement_id": str(history.get("movement_id") or movement.get("movement_id") or ""),
                        "history_id": str(history.get("id") or ""),
                        "value": value,
                    })
    rows = []
    for day in sorted(by_date):
        item = by_date[day]
        legacy = item["legacy_values"]
        values = list(dict.fromkeys(entry["value"] for entry in legacy if entry["value"]))
        if not values:
            decision = "daily_record_only"
        elif item["daily_value"] and all(value == item["daily_value"] for value in values):
            decision = "same_cleanup"
        elif not item["daily_value"] and len(values) == 1:
            decision = "migrate_to_daily_record"
        else:
            decision = "conflict_manual_review"
        rows.append({"date": day, "daily_value": item["daily_value"], "legacy_values": legacy, "decision": decision})
    return {
        "schema": "cardio-ownership-v1",
        "source_of_truth": "DailyRecord.Cardio",
        "rows": rows,
        "counts": {
            "migrate_to_daily_record": sum(row["decision"] == "migrate_to_daily_record" for row in rows),
            "same_cleanup": sum(row["decision"] == "same_cleanup" for row in rows),
            "conflict_manual_review": sum(row["decision"] == "conflict_manual_review" for row in rows),
        },
    }


def _apply_unambiguous_cardio_migration(database: dict, report: dict) -> None:
    preview = cardio_migration_preview(database)
    report["cardio_migration"] = preview
    for row in preview["rows"]:
        if row["decision"] not in {"migrate_to_daily_record", "same_cleanup"}:
            continue
        day = row["date"]
        if row["decision"] == "migrate_to_daily_record":
            target = next((item for item in _rows(database, "daily_records") if canonical_date(item.get("Date")) == day), None)
            if target is None:
                target = {
                    "id": _stable_id("daily-cardio", day),
                    "Date": day,
                    "source": "cardio migration",
                    "record_day_id": record_day_id(day),
                    "revision": 1,
                    "updated_at": f"{day}T00:00:00",
                }
                database.setdefault("daily_records", []).append(target)
            value = next(entry["value"] for entry in row["legacy_values"] if entry["value"])
            if str(target.get("Cardio", "") or "").strip() != value:
                target["Cardio"] = value
                target["updated_at"] = now_iso()
                report["changed"] = True
        for session in _rows(database, "training_sessions"):
            if canonical_date(session.get("Date")) == day and "Cardio" in session:
                session.pop("Cardio", None)
                report["changed"] = True
        for movement in _movement_rows(database):
            for history in movement.get("history", []) or []:
                if canonical_date(history.get("date")) == day and "cardio" in history:
                    history.pop("cardio", None)
                    report["changed"] = True


def _rebuild_movement_projection(database: dict) -> None:
    """Rebuild the old ``movements`` shape from canonical session items."""
    _compatibility_event("movement_projection_rebuild")
    previous = database.get("movements") or {}
    projected: dict[str, dict] = {}
    for session in _rows(database, "training_sessions"):
        for item in session.get("movement_items", []) or []:
            if not isinstance(item, dict):
                continue
            movement_id = str(item.get("movement_id") or "").strip()
            if not movement_id:
                continue
            previous_row = previous.get(movement_id, {}) if isinstance(previous, dict) else {}
            current = projected.setdefault(
                movement_id,
                {
                    "movement_id": movement_id,
                    "name": str(item.get("display_name") or item.get("name") or movement_id),
                    "aliases": [],
                    "history": [],
                    "created_at": str(
                        previous_row.get("created_at")
                        or item.get("updated_at")
                        or item.get("date")
                        or ""
                    ),
                    "projection": MOVEMENT_ITEMS_SCHEMA_VERSION,
                },
            )
            current["history"].append(copy.deepcopy(item))
    for movement_key, old in previous.items() if isinstance(previous, dict) else []:
        if not isinstance(old, dict):
            continue
        # Legacy files can contain a compatibility row keyed by an old map
        # key while carrying the same movement_id as the canonical row that
        # was just projected from session items.  Keep one identity in the
        # projection and merge the legacy context into that row instead of
        # manufacturing a second row with the same movement_id.
        movement_id = str(old.get("movement_id") or movement_key).strip()
        if movement_id in projected:
            current = projected[movement_id]
            for key, value in old.items():
                if key not in current:
                    current[key] = copy.deepcopy(value)
            current["aliases"] = list(dict.fromkeys([
                *(current.get("aliases") or []),
                *(old.get("aliases") or []),
            ]))
            existing_history = current.setdefault("history", [])
            existing_keys = {
                str(item.get("movement_instance_id") or item.get("id") or "")
                for item in existing_history
                if isinstance(item, dict)
            }
            for item in old.get("history", []) or []:
                if not isinstance(item, dict):
                    continue
                item_key = str(item.get("movement_instance_id") or item.get("id") or "")
                if item_key and item_key in existing_keys:
                    continue
                existing_history.append(copy.deepcopy(item))
                if item_key:
                    existing_keys.add(item_key)
            continue
        projected[movement_id] = copy.deepcopy(old)
        projected[movement_id]["movement_id"] = movement_id
        projected[movement_id]["projection"] = "legacy-unresolved"
    for movement_id, item in projected.items():
        old = previous.get(movement_id, {}) if isinstance(previous, dict) else {}
        item["name"] = str(old.get("name") or item.get("name") or movement_id)
        item["aliases"] = list(dict.fromkeys([*(old.get("aliases") or []), *(item.get("aliases") or [])]))
        item["history"] = sorted(
            item.get("history", []) or [],
            key=lambda row: (canonical_date(row.get("date")), int(row.get("order") or 9999), str(row.get("movement_instance_id") or row.get("id") or "")),
        )
    database["movements"] = projected


rebuild_movement_projection = _rebuild_movement_projection


def migrate_state(database: dict, dictionary: dict) -> tuple[dict, dict, dict]:
    """Return a normalized in-memory copy and migration report.

    This function never touches a file.  The command service is responsible
    for the existing paired checkpoint/atomic-write boundary when a migration
    is explicitly confirmed.
    """
    db = copy.deepcopy(database if isinstance(database, dict) else {})
    lexicon = copy.deepcopy(dictionary if isinstance(dictionary, dict) else {})
    report = {
        "changed": False,
        "added_fields": 0,
        "record_days": 0,
        "raw_revisions": 0,
        "movement_items": 0,
        "movement_projection": MOVEMENT_ITEMS_SCHEMA_VERSION,
    }
    for key in ("daily_records", "diet_records", "training_sessions", "raw_entries", "data_module_records", "record_days", "raw_entry_revisions"):
        db.setdefault(key, [])
    db.setdefault("movements", {})

    def mark(changed: bool) -> None:
        if changed:
            report["changed"] = True
            report["added_fields"] += 1

    dates: set[str] = set()
    for collection, date_field in (("daily_records", "Date"), ("diet_records", "Date"), ("training_sessions", "Date"), ("data_module_records", "date"), ("raw_entries", "date")):
        for row in _rows(db, collection):
            dates.add(canonical_date(row.get(date_field)))
            mark(_touch_entity(row, canonical_date(row.get(date_field))))
    canonical_state = db.get("movement_items_schema_version") == MOVEMENT_ITEMS_SCHEMA_VERSION
    for movement in _movement_rows(db) if not canonical_state else []:
        # Legacy movement rows and their history are input-only projection
        # data.  Do not stamp bookkeeping fields onto them during migration;
        # the rebuilt projection must remain idempotent.
        for history in movement.get("history", []) or []:
            dates.add(canonical_date(history.get("date")))

    days_by_id = {str(row.get("record_day_id")): row for row in _rows(db, "record_days") if row.get("record_day_id")}
    days_by_date = {canonical_date(row.get("date")): row for row in _rows(db, "record_days") if canonical_date(row.get("date"))}
    for day in sorted(item for item in dates if item):
        day_id = record_day_id(day)
        row = days_by_id.get(day_id) or days_by_date.get(day)
        if row is None:
            row = {"record_day_id": day_id, "date": day, "revision": 1, "created_at": f"{day}T00:00:00", "updated_at": f"{day}T00:00:00"}
            db["record_days"].append(row)
            days_by_id[day_id] = row
            days_by_date[day] = row
            report["record_days"] += 1
            report["changed"] = True
        if row.get("record_day_id") != day_id:
            row["record_day_id"] = day_id
            report["changed"] = True
        row.setdefault("date", day)
        row.setdefault("revision", 1)
        row.setdefault("updated_at", row.get("created_at", f"{day}T00:00:00"))

    for collection, date_field in (("daily_records", "Date"), ("diet_records", "Date"), ("training_sessions", "Date"), ("data_module_records", "date"), ("raw_entries", "date")):
        for row in _rows(db, collection):
            day = canonical_date(row.get(date_field))
            if day and row.get("record_day_id") != record_day_id(day):
                row["record_day_id"] = record_day_id(day)
                report["changed"] = True

    raw_by_id = {str(row.get("id")): row for row in _rows(db, "raw_entries") if row.get("id")}
    for raw in _rows(db, "raw_entries"):
        if not raw.get("id"):
            raw["id"] = _stable_id("raw", {"date": raw.get("date"), "text": raw.get("text", "")})
            raw_by_id[str(raw["id"])] = raw
            report["changed"] = True
        raw_id = str(raw["id"])
        raw_revision_id = str(raw.get("raw_revision_id") or f"rawrev:{raw_id}:1")
        revisions = [item for item in _rows(db, "raw_entry_revisions") if str(item.get("raw_entry_id")) == raw_id]
        if not revisions:
            db["raw_entry_revisions"].append({"raw_revision_id": raw_revision_id, "raw_entry_id": raw_id, "record_day_id": record_day_id(raw.get("date")), "date": canonical_date(raw.get("date")), "revision": 1, "text": str(raw.get("text", "")), "created_at": raw.get("created_at", ""), "updated_at": raw.get("updated_at", raw.get("created_at", "")), "source": raw.get("source", "legacy")})
            report["raw_revisions"] += 1
            report["changed"] = True
        raw["raw_revision_id"] = raw_revision_id
        raw.setdefault("revision", 1)
        raw.setdefault("updated_at", raw.get("created_at", ""))
        raw.setdefault("record_day_id", record_day_id(raw.get("date")))
        for revision in [item for item in _rows(db, "raw_entry_revisions") if str(item.get("raw_entry_id")) == raw_id]:
            revision.setdefault("raw_revision_id", raw_revision_id)
            revision.setdefault("revision", 1)
            revision.setdefault("record_day_id", record_day_id(revision.get("date")))
            revision.setdefault("date", canonical_date(raw.get("date")))
            revision.setdefault("updated_at", revision.get("created_at", ""))

    for definition in lexicon.get("movements", []) or []:
        if not isinstance(definition, dict):
            continue
        if not definition.get("revision"):
            definition["revision"] = 1
            report["changed"] = True
        if "updated_at" not in definition:
            definition["updated_at"] = definition.get("created_at", "")
            report["changed"] = True

    sessions = _rows(db, "training_sessions")
    for session in sessions:
        session_date = canonical_date(session.get("Date"))
        raw_text = str(session.get("Raw Record", "")).strip()
        candidates = [raw for raw in _rows(db, "raw_entries") if canonical_date(raw.get("date")) == session_date and not raw.get("superseded")]
        exact = [raw for raw in candidates if str(raw.get("text", "")).strip() == raw_text and raw_text]
        linked = exact[0] if len(exact) == 1 else candidates[0] if len(candidates) == 1 else None
        if linked:
            for key, value in (("raw_entry_id", linked.get("id")), ("raw_revision_id", linked.get("raw_revision_id"))):
                if session.get(key) != value:
                    session[key] = value
                    report["changed"] = True
        session.setdefault("record_day_id", record_day_id(session_date))
        session.setdefault("movement_items", [])
        if not isinstance(session["movement_items"], list):
            session["movement_items"] = []
            report["changed"] = True

    existing_items_by_id = {
        str(item.get("movement_instance_id") or item.get("id")): item
        for session in sessions
        for item in session.get("movement_items", []) or []
        if isinstance(item, dict) and str(item.get("movement_instance_id") or item.get("id"))
    }
    existing_ids = set(existing_items_by_id)
    for history in _legacy_history(db) if not canonical_state else []:
        history_id = str(history.get("movement_instance_id") or history.get("id") or "")
        if history_id and history_id in existing_ids:
            existing = existing_items_by_id[history_id]
            if str(existing.get("movement_id") or "") != str(history.get("movement_id") or ""):
                report.setdefault("movement_conflicts", []).append({
                    "type": "duplicate_history_id",
                    "history_id": history_id,
                    "existing_movement_id": str(existing.get("movement_id") or ""),
                    "legacy_movement_id": str(history.get("movement_id") or ""),
                })
            continue
        candidates = _session_candidates(sessions, history)
        if not candidates:
            legacy_date = canonical_date(history.get("date"))
            legacy_day = str(history.get("training_day", "")).strip()
            if legacy_date:
                synthetic_id = _stable_id("legacy-training-session", {"date": legacy_date, "training_day": legacy_day})
                synthetic = {
                    "id": synthetic_id,
                    "No.": history.get("training_day", ""),
                    "Date": legacy_date,
                    "Split": "",
                    "Raw Record": "",
                    "Standardized Summary": "",
                    "Notes": "",
                    "source": "legacy movement migration",
                    "record_day_id": record_day_id(legacy_date),
                    "movement_items": [],
                    "revision": 1,
                    "updated_at": f"{legacy_date}T00:00:00",
                }
                sessions.append(synthetic)
                candidates = [synthetic]
        if len(candidates) != 1:
            report.setdefault("movement_conflicts", []).append({"movement_instance_id": history_id, "movement_id": history.get("movement_id", ""), "date": canonical_date(history.get("date")), "training_day": history.get("training_day", ""), "candidate_session_ids": [str(row.get("id")) for row in candidates]})
            continue
        item = _movement_item_from_history(history, candidates[0])
        candidates[0]["movement_items"].append(item)
        existing_ids.add(item["movement_instance_id"])
        existing_items_by_id[item["movement_instance_id"]] = item
        report["movement_items"] += 1
        report["changed"] = True

    # Synthetic sessions created above can now be linked to their sole raw
    # entry as well; doing this in the same pass keeps migration idempotent.
    for session in sessions:
        if session.get("raw_entry_id"):
            continue
        session_date = canonical_date(session.get("Date"))
        candidates = [raw for raw in _rows(db, "raw_entries") if canonical_date(raw.get("date")) == session_date and not raw.get("superseded")]
        if len(candidates) == 1:
            linked = candidates[0]
            session["raw_entry_id"] = linked.get("id", "")
            session["raw_revision_id"] = linked.get("raw_revision_id", "")
            report["changed"] = True

    session_by_id = {str(row.get("id")): row for row in sessions if row.get("id")}
    for session in sessions:
        for item in session.get("movement_items", []) or []:
            if not isinstance(item, dict):
                continue
            item["movement_instance_id"] = str(item.get("movement_instance_id") or item.get("id") or _stable_id("movement-instance", item))
            item["id"] = item["movement_instance_id"]
            item["training_session_id"] = str(session.get("id", ""))
            item["record_day_id"] = str(session.get("record_day_id") or record_day_id(session.get("Date")))
            item.pop("cardio", None)
            item.setdefault("movement_id", "")
            item.setdefault("sets", [])
            item.setdefault("notes", "")
            item.setdefault("raw", "")
            item.setdefault("exclude_from_progress", False)
            item.setdefault("revision", 1)
            item.setdefault(
                "updated_at",
                str(item.get("date") or session.get("Date") or "")[:10] + "T00:00:00"
                if str(item.get("date") or session.get("Date") or "")[:10]
                else "",
            )
            linked = session_by_id.get(str(item.get("training_session_id")))
            if linked:
                item.setdefault("raw_entry_id", linked.get("raw_entry_id", ""))
                item.setdefault("raw_revision_id", linked.get("raw_revision_id", ""))

    db, organization_changed = normalize_training_organization(db, lexicon)
    if organization_changed:
        report["training_organization"] = True

    _apply_unambiguous_cardio_migration(db, report)
    _rebuild_movement_projection(db)
    db["record_schema_version"] = RELATION_SCHEMA_VERSION
    db["movement_items_schema_version"] = MOVEMENT_ITEMS_SCHEMA_VERSION
    return db, lexicon, report


def movement_items(database: dict, movement_id: str = "") -> list[dict]:
    rows = []
    for session in _rows(database, "training_sessions"):
        for item in session.get("movement_items", []) or []:
            if not isinstance(item, dict):
                continue
            if movement_id and str(item.get("movement_id")) != str(movement_id):
                continue
            rows.append(item)
    return rows


def movement_items_by_session(database: dict, session_id: str) -> list[dict]:
    return [item for item in movement_items(database) if str(item.get("training_session_id")) == str(session_id)]


def movement_items_by_date(database: dict, entry_date: str) -> list[dict]:
    day = canonical_date(entry_date)
    day_id = record_day_id(day)
    return [item for item in movement_items(database) if canonical_date(item.get("date")) == day or str(item.get("record_day_id")) == day_id]


def validate_relations(database: dict, dictionary: dict) -> list[dict]:
    """Return invariant violations; an empty list means the graph is sound."""
    if database.get("record_schema_version") != RELATION_SCHEMA_VERSION:
        return []
    issues: list[dict] = []
    days = {str(row.get("record_day_id")): row for row in _rows(database, "record_days") if row.get("record_day_id")}
    sessions = {str(row.get("id")): row for row in _rows(database, "training_sessions") if row.get("id")}
    raw = {str(row.get("id")): row for row in _rows(database, "raw_entries") if row.get("id")}
    definitions = {str(row.get("movement_id")) for row in (dictionary.get("movements", []) if isinstance(dictionary, dict) else []) if row.get("movement_id")}
    for collection, date_field in (("daily_records", "Date"), ("diet_records", "Date"), ("training_sessions", "Date"), ("data_module_records", "date")):
        for row in _rows(database, collection):
            expected = record_day_id(row.get(date_field))
            if expected and str(row.get("record_day_id")) != expected:
                issues.append({"code": "RECORD_DAY_MISMATCH", "collection": collection, "id": row.get("id")})
            if expected and expected not in days:
                issues.append({"code": "MISSING_RECORD_DAY", "collection": collection, "id": row.get("id")})
    instance_ids: set[str] = set()
    for session in _rows(database, "training_sessions"):
        for item in session.get("movement_items", []) or []:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("movement_instance_id") or item.get("id") or "")
            if item_id in instance_ids:
                issues.append({"code": "DUPLICATE_MOVEMENT_INSTANCE_ID", "movement_instance_id": item_id})
            instance_ids.add(item_id)
            if str(item.get("training_session_id")) not in sessions:
                issues.append({"code": "ORPHAN_TRAINING_SESSION", "movement_instance_id": item_id})
            if not str(item.get("movement_id") or ""):
                issues.append({"code": "MOVEMENT_ID_MISSING", "movement_instance_id": item_id})
            elif definitions and str(item.get("movement_id")) not in definitions:
                issues.append({"code": "MISSING_MOVEMENT_DEFINITION", "movement_id": item.get("movement_id")})
            if "cardio" in item:
                issues.append({"code": "CARDIO_ON_MOVEMENT_ITEM", "movement_instance_id": item_id})
            raw_id = str(item.get("raw_entry_id", ""))
            if raw_id and raw_id not in raw:
                issues.append({"code": "ORPHAN_RAW_ENTRY", "movement_instance_id": item_id})
    return issues


__all__ = [
    "RELATION_SCHEMA_VERSION",
    "MOVEMENT_ITEMS_SCHEMA_VERSION",
    "canonical_date",
    "record_day_id",
    "now_iso",
    "migrate_state",
    "cardio_migration_preview",
    "compatibility_diagnostics",
    "movement_items",
    "movement_items_by_session",
    "movement_items_by_date",
    "rebuild_movement_projection",
    "validate_relations",
]
