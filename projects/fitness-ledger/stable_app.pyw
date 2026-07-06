from __future__ import annotations

import json
import os
import re
import shutil
import sys
import uuid
from datetime import date, datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from ledger_commands import LedgerCommandError, LedgerCommandService


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_FILE = DATA_DIR / "tracker.json"
HISTORY_FILE = DATA_DIR / "history_import.json"
MOVEMENT_DICTIONARY_FILE = DATA_DIR / "movement_dictionary.json"
DATA_CHECK_STATE_FILE = DATA_DIR / "data_check_state.json"
BACKUP_DIR = DATA_DIR / "backups"
ICON_FILE = BASE_DIR / "assets" / "fitness-ledger.ico"
ICON_PNG = BASE_DIR / "assets" / "fitness-ledger.png"

COLORS = {
    "navy": "#17233C",
    "navy_2": "#223454",
    "cream": "#F4F0E7",
    "paper": "#FFFCF6",
    "stone": "#E7E0D4",
    "ink": "#222831",
    "muted": "#6E706F",
    "teal": "#2E7168",
    "teal_2": "#245D56",
    "orange": "#D78636",
    "red": "#A84D45",
    "white": "#FFFFFF",
}

def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def today_text() -> str:
    return date.today().isoformat()


def read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f"{path.name}.tmp")
    payload = json.dumps(value, ensure_ascii=False, indent=2)
    temp.write_text(payload, encoding="utf-8")
    json.loads(temp.read_text(encoding="utf-8"))
    temp.replace(path)


def backup_file(path: Path, prefix: str) -> Path | None:
    if not path.exists():
        return None
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target = BACKUP_DIR / f"{prefix}_{stamp}.json"
    shutil.copy2(path, target)
    return target


def backup_data(prefix: str = "tracker") -> Path | None:
    return backup_file(DATA_FILE, prefix)


def create_undo_checkpoint() -> tuple[Path | None, Path | None]:
    try:
        json.loads(DATA_FILE.read_text(encoding="utf-8"))
        json.loads(MOVEMENT_DICTIONARY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None, None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    tracker_backup = BACKUP_DIR / f"undo_tracker_{stamp}.json"
    dictionary_backup = BACKUP_DIR / f"undo_dictionary_{stamp}.json"
    shutil.copy2(DATA_FILE, tracker_backup)
    shutil.copy2(MOVEMENT_DICTIONARY_FILE, dictionary_backup)
    return tracker_backup, dictionary_backup


def normalize_name(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[\s_\-/（）()]+", "", value)
    value = re.sub(r"[^\w\u4e00-\u9fff]", "", value)
    return value


def load_movement_dictionary() -> dict:
    data = read_json(MOVEMENT_DICTIONARY_FILE, {"version": "1.0", "movements": []})
    movements = data.get("movements") if isinstance(data, dict) else []
    if not isinstance(movements, list):
        movements = []
    return {"version": str(data.get("version", "1.0")), "movements": movements}


def movement_definition_index(dictionary: dict) -> tuple[dict, dict]:
    by_id = {}
    by_alias = {}
    for definition in dictionary.get("movements") or []:
        movement_id = str(definition.get("movement_id", "")).strip()
        if not movement_id:
            continue
        by_id[movement_id] = definition
        names = [
            definition.get("display_name", ""),
            definition.get("english_name", ""),
            *(definition.get("aliases") or []),
        ]
        for name in names:
            normalized = normalize_name(str(name))
            if normalized:
                by_alias[normalized] = definition
    return by_id, by_alias


def find_movement_definition(value: str, dictionary: dict) -> dict | None:
    by_id, by_alias = movement_definition_index(dictionary)
    return by_id.get(str(value).strip()) or by_alias.get(normalize_name(value))


def next_custom_movement_id(dictionary: dict) -> str:
    used = {
        int(match.group(1))
        for definition in dictionary.get("movements") or []
        if (match := re.fullmatch(r"CUSTOM_(\d+)", str(definition.get("movement_id", ""))))
    }
    number = 1
    while number in used:
        number += 1
    return f"CUSTOM_{number:03d}"


def add_custom_movement_definition(candidate: str, dictionary: dict) -> dict:
    display_name = title_case_movement(candidate)
    definition = {
        "movement_id": next_custom_movement_id(dictionary),
        "display_name": display_name,
        "english_name": display_name if not re.search(r"[\u4e00-\u9fff]", display_name) else "",
        "aliases": [candidate],
        "muscle_group": "Unclassified",
        "category": "Strength",
        "equipment": "",
        "active": True,
        "notes": "Automatically registered from a confirmed training entry.",
    }
    dictionary.setdefault("movements", []).append(definition)
    write_json(MOVEMENT_DICTIONARY_FILE, dictionary)
    return definition


def migrate_movement_references(database: dict, dictionary: dict) -> tuple[int, bool]:
    migrated = 0
    changed = False
    for movement in database.get("movements", {}).values():
        candidates = [
            movement.get("movement_id", ""),
            movement.get("name", ""),
            *(movement.get("aliases") or []),
        ]
        definition = None
        for candidate in candidates:
            if candidate:
                definition = find_movement_definition(str(candidate), dictionary)
            if definition:
                break
        if not definition:
            continue
        movement_id = definition["movement_id"]
        if movement.get("movement_id") != movement_id:
            movement["movement_id"] = movement_id
            changed = True
        for history in movement.get("history") or []:
            if history.get("movement_id") != movement_id:
                history["movement_id"] = movement_id
                changed = True
        migrated += 1
    return migrated, changed


def title_case_movement(value: str) -> str:
    value = " ".join(value.strip(" .,:;，；").split())
    if re.search(r"[\u4e00-\u9fff]", value):
        return value
    return value.title()


def parse_number(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, re.I)
    return float(match.group(1)) if match else None


def parse_date(text: str) -> str:
    full = re.search(r"\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b", text)
    if full:
        return f"{int(full.group(1)):04d}-{int(full.group(2)):02d}-{int(full.group(3)):02d}"
    short = re.search(r"(?m)^\s*(\d{1,2})[./](\d{1,2})\s*$", text)
    if short:
        return f"{date.today().year:04d}-{int(short.group(1)):02d}-{int(short.group(2)):02d}"
    return today_text()


def extract_load_blocks(text: str) -> list[dict]:
    blocks = []
    consumed = []
    progression_pattern = (
        r"\((?P<weights>\d+(?:\.\d+)?(?:\s*[-－]\s*\d+(?:\.\d+)?)+)\)"
        r"\s*[x×*]\s*(?P<reps>\d+)\s*[x×*]\s*(?P<sets>\d+)"
    )
    for match in re.finditer(progression_pattern, text, re.I):
        weights = re.split(r"\s*[-－]\s*", match.group("weights"))
        for weight in weights:
            blocks.append(
                {
                    "weight": float(weight),
                    "reps": int(match.group("reps")),
                    "sets": int(match.group("sets")),
                }
            )
        consumed.append(match.span())

    searchable = text
    for start, end in reversed(consumed):
        searchable = searchable[:start] + (" " * (end - start)) + searchable[end:]
    patterns = [
        r"(?P<weight>\d+(?:\.\d+)?)\s*(?:kg|公斤|千克)?\s*[x×*]\s*(?P<reps>\d+)\s*(?:次|reps?)?\s*[x×*]\s*(?P<sets>\d+)\s*(?:组|sets?)?",
        r"(?P<weight>\d+(?:\.\d+)?)\s*(?:kg|公斤|千克)?\s*[-－]\s*(?P<reps>\d+)\s*[-－]\s*(?P<sets>\d+)",
        r"(?P<weight>\d+(?:\.\d+)?)\s*(?:kg|公斤|千克)\s*(?P<reps>\d+)\s*次\s*(?P<sets>\d+)\s*组",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, searchable, re.I):
            item = {
                "weight": float(match.group("weight")),
                "reps": int(match.group("reps")),
                "sets": int(match.group("sets")),
            }
            if item not in blocks:
                blocks.append(item)
    return blocks


def extract_load_blocks(text: str) -> list[dict]:
    blocks = []
    normalized = (
        str(text or "")
        .replace("×", "x")
        .replace("X", "x")
        .replace("*", "x")
        .replace("，", ",")
        .replace("；", ";")
    )

    progression_pattern = (
        r"\((?P<weights>\d+(?:\.\d+)?(?:\s*[-,;]\s*\d+(?:\.\d+)?)+)\)"
        r"\s*x\s*(?P<reps>\d+)\s*x\s*(?P<sets>\d+)"
    )
    consumed = []
    for match in re.finditer(progression_pattern, normalized, re.I):
        for weight in re.split(r"\s*[-,;]\s*", match.group("weights")):
            item = {
                "weight": float(weight),
                "reps": int(match.group("reps")),
                "sets": int(match.group("sets")),
            }
            if item not in blocks:
                blocks.append(item)
        consumed.append(match.span())

    searchable = normalized
    for start, end in reversed(consumed):
        searchable = searchable[:start] + (" " * (end - start)) + searchable[end:]

    patterns = [
        r"(?P<weight>\d+(?:\.\d+)?)\s*(?:kg|公斤|千克)?\s*x\s*(?P<reps>\d+)\s*(?:次|reps?)?\s*x\s*(?P<sets>\d+)\s*(?:组|sets?)?",
        r"(?P<weight>\d+(?:\.\d+)?)\s*(?:kg|公斤|千克)?\s*-\s*(?P<reps>\d+)\s*-\s*(?P<sets>\d+)",
        r"(?P<weight>\d+(?:\.\d+)?)\s*(?:kg|公斤|千克)\s*(?P<reps>\d+)\s*次\s*(?P<sets>\d+)\s*组",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, searchable, re.I):
            item = {
                "weight": float(match.group("weight")),
                "reps": int(match.group("reps")),
                "sets": int(match.group("sets")),
            }
            if item not in blocks:
                blocks.append(item)
    return blocks


def extract_cardio_metrics(text: str) -> dict:
    duration = parse_number(r"(\d+(?:\.\d+)?)\s*(?:分钟|min(?:ute)?s?)", text)
    incline = parse_number(r"(?:坡度|incline)\s*[:：]?\s*(\d+(?:\.\d+)?)", text)
    speed = parse_number(r"(?:速度|speed)\s*[:：]?\s*(\d+(?:\.\d+)?)", text)
    heart_rate = parse_number(r"(?:心率|heart\s*rate)\s*[:：]?\s*(\d+(?:\.\d+)?)", text)
    return {
        "duration_minutes": duration,
        "incline": incline,
        "speed": speed,
        "heart_rate": heart_rate,
    }


def extract_labeled_section(text: str, labels: tuple[str, ...], stop_labels: tuple[str, ...]) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    stop_pattern = "|".join(re.escape(label) for label in stop_labels)
    match = re.search(
        rf"(?ms)^(?:{label_pattern})\s*[:：]\s*(.*?)(?=^(?:{stop_pattern})\s*[:：]|\Z)",
        text,
        re.I,
    )
    return match.group(1).strip() if match else ""


def extract_training_section(text: str) -> tuple[str, str]:
    match = re.search(
        r"(?ms)^(?:training|训练)[ \t]*[:：][ \t]*([^\r\n]*)"
        r"(?:\r?\n)?(.*?)(?=^(?:cardio|有氧|diet|饮食|notes?|备注)[ \t]*[:：]|\Z)",
        text,
        re.I,
    )
    if not match:
        return "", ""
    return match.group(1).strip(), match.group(2).strip()


def extract_bowel_movement(text: str) -> str:
    explicit = re.search(r"(?im)^\s*(?:排便|bowel(?:\s+movement)?)\s*[:：]\s*(.+?)\s*$", text)
    if explicit:
        value = explicit.group(1).strip()
        lowered = value.lower()
        if lowered in {"yes", "y"}:
            return "有"
        if lowered in {"no", "n", "none"}:
            return "无"
        if value in {"有", "有排便"}:
            return "有"
        if value in {"无", "没有", "无排便"}:
            return "无"
        return value
    if re.search(r"(今日|今天).{0,6}(排便正常|正常排便)", text):
        return "正常"
    if re.search(r"(今日|今天).{0,6}(没有排便|无排便|没排便)", text):
        return "无"
    if re.search(r"(今日|今天).{0,6}(有排便|排便)", text):
        return "有"
    return ""


def compact_section_lines(text: str) -> str:
    return "\n".join(line.strip() for line in str(text or "").splitlines() if line.strip())


def format_number(value) -> str:
    if value is None or value == "":
        return ""
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return str(value)


def make_cell_preview(text, max_len=28) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= max_len:
        return value
    return f"{value[: max(1, max_len - 3)].rstrip()}..."


def format_set_summary(record: dict) -> str:
    sets = record.get("sets") or []
    if sets:
        return ", ".join(
            f"{format_number(item.get('weight'))}kg×{format_number(item.get('reps'))}×{format_number(item.get('sets'))}"
            for item in sets
        )

    cardio = record.get("cardio") or {}
    cardio_parts = []
    if cardio.get("duration_minutes") is not None:
        cardio_parts.append(f"{format_number(cardio['duration_minutes'])}min")
    if cardio.get("heart_rate") is not None:
        cardio_parts.append(f"HR{format_number(cardio['heart_rate'])}")
    if cardio.get("incline") is not None:
        cardio_parts.append(f"incline {format_number(cardio['incline'])}")
    if cardio.get("speed") is not None:
        cardio_parts.append(f"speed {format_number(cardio['speed'])}")
    return " ".join(cardio_parts) or str(record.get("raw", "")).strip()


def format_matrix_cell(record: dict) -> str:
    day = record.get("training_day")
    order = record.get("order")
    prefix = []
    if day not in (None, ""):
        prefix.append(f"Day {day}")
    if order not in (None, ""):
        prefix.append(f"Ex {order}")
    details = format_set_summary(record)
    if details:
        prefix.append(details)
    return " / ".join(prefix)


def is_cardio_line(text: str) -> bool:
    return bool(re.search(r"跑步机|有氧|步行|快走|treadmill|cardio|walk", text, re.I))


def strip_movement_metrics(text: str) -> str:
    value = re.sub(r"^\s*\d+\s*[.、)]\s*", "", text)
    metric_start = re.search(
        r"\d+(?:\.\d+)?\s*(?:kg|公斤|千克)?\s*(?:[x×*－-]|\d+\s*次)",
        value,
        re.I,
    )
    if metric_start:
        value = value[: metric_start.start()]
    return title_case_movement(value)


def build_set_item(weight_text: str, reps: str, sets: str) -> dict:
    raw_weight = str(weight_text).strip()
    if re.fullmatch(r"\d+(?:\.\d+)?", raw_weight):
        weight = float(raw_weight)
        label = ""
    else:
        weight = None
        label = raw_weight
    return {
        "weight": weight,
        "weight_text": label,
        "reps": int(reps),
        "sets": int(sets),
    }


def extract_load_blocks(text: str) -> list[dict]:
    blocks = []
    normalized = str(text or "").replace("脳", "x").replace("X", "x").replace("*", "x").replace("锛?", ",")
    progression_pattern = (
        r"\((?P<weights>\d+(?:\.\d+)?(?:\s*[-,;]\s*\d+(?:\.\d+)?)+)\)"
        r"\s*x\s*(?P<reps>\d+)\s*x\s*(?P<sets>\d+)"
    )
    consumed = []
    for match in re.finditer(progression_pattern, normalized, re.I):
        for weight in re.split(r"\s*[-,;]\s*", match.group("weights")):
            item = build_set_item(weight, match.group("reps"), match.group("sets"))
            if item not in blocks:
                blocks.append(item)
        consumed.append(match.span())

    searchable = normalized
    for start, end in reversed(consumed):
        searchable = searchable[:start] + (" " * (end - start)) + searchable[end:]

    patterns = [
        r"(?P<weight>自重|bodyweight|\d+(?:\.\d+)?)\s*(?:kg|鍏枻|鍗冨厠)?\s*x\s*(?P<reps>\d+)\s*(?:娆reps?)?\s*x\s*(?P<sets>\d+)\s*(?:缁剕sets?)?",
        r"(?P<weight>自重|bodyweight|\d+(?:\.\d+)?)\s*(?:kg|鍏枻|鍗冨厠)?\s*-\s*(?P<reps>\d+)\s*-\s*(?P<sets>\d+)",
        r"(?P<weight>自重|bodyweight|\d+(?:\.\d+)?)\s*(?:kg|鍏枻|鍗冨厠)?\s*(?P<reps>\d+)\s*娆s*(?P<sets>\d+)\s*缁?",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, searchable, re.I):
            item = build_set_item(match.group("weight"), match.group("reps"), match.group("sets"))
            if item not in blocks:
                blocks.append(item)
    return blocks


def extract_training_section(text: str) -> tuple[str, str]:
    lines = str(text or "").splitlines()
    split = ""
    body_lines = []
    in_training = False
    for line in lines:
        if not in_training:
            match = re.match(r"^\s*(?:training|璁粌)\s*[:锛歖\s*(.*)$", line, re.I)
            if match:
                split = match.group(1).strip()
                in_training = True
            continue
        if re.match(r"^\s*(?:cardio|鏈夋哀|diet|楗)\s*[:锛歖", line, re.I):
            break
        body_lines.append(line)
    return split, "\n".join(body_lines).strip()


def extract_global_notes_section(text: str) -> str:
    matches = list(re.finditer(r"(?im)^\s*(?:notes?|澶囨敞)\s*[:锛歖\s*(.*)$", str(text or "")))
    if not matches:
        return ""
    return matches[-1].group(1).strip()


def format_set_weight(item: dict) -> str:
    weight_text = str(item.get("weight_text", "")).strip()
    if weight_text:
        return weight_text
    weight = item.get("weight")
    if weight in (None, ""):
        return ""
    return f"{format_number(weight)}kg"


def format_set_summary(record: dict) -> str:
    sets = record.get("sets") or []
    if sets:
        return ", ".join(
            f"{format_set_weight(item)}脳{format_number(item.get('reps'))}脳{format_number(item.get('sets'))}"
            for item in sets
        )

    cardio = record.get("cardio") or {}
    cardio_parts = []
    if cardio.get("duration_minutes") is not None:
        cardio_parts.append(f"{format_number(cardio['duration_minutes'])}min")
    if cardio.get("heart_rate") is not None:
        cardio_parts.append(f"HR{format_number(cardio['heart_rate'])}")
    if cardio.get("incline") is not None:
        cardio_parts.append(f"incline {format_number(cardio['incline'])}")
    if cardio.get("speed") is not None:
        cardio_parts.append(f"speed {format_number(cardio['speed'])}")
    return " ".join(cardio_parts) or str(record.get("raw", "")).strip()


def blank_database() -> dict:
    return {
        "version": 1,
        "created_at": now_iso(),
        "daily_records": [],
        "diet_records": [],
        "training_sessions": [],
        "movements": {},
        "raw_entries": [],
    }


def import_history() -> dict:
    database = blank_database()
    dictionary = load_movement_dictionary()
    history = read_json(HISTORY_FILE, {})
    sheets = history.get("sheets", {})

    daily = sheets.get("Daily Log") or []
    if daily:
        headers = [str(value or "") for value in daily[0]]
        for row in daily[1:]:
            record = {headers[index]: value for index, value in enumerate(row) if index < len(headers)}
            record["id"] = str(uuid.uuid4())
            record["source"] = "fitness_tracker_clean_en.xlsx"
            database["daily_records"].append(record)

    diets = sheets.get("Diet Log") or []
    if diets:
        headers = [str(value or "") for value in diets[0]]
        for row in diets[1:]:
            record = {headers[index]: value for index, value in enumerate(row) if index < len(headers)}
            record["id"] = str(uuid.uuid4())
            record["source"] = "fitness_tracker_clean_en.xlsx"
            database["diet_records"].append(record)

    sessions = sheets.get("Training Log") or []
    day_by_date = {}
    if sessions:
        headers = [str(value or "") for value in sessions[0]]
        for row in sessions[1:]:
            record = {headers[index]: value for index, value in enumerate(row) if index < len(headers)}
            record["id"] = str(uuid.uuid4())
            record["source"] = "fitness_tracker_clean_en.xlsx"
            database["training_sessions"].append(record)
            day_by_date[str(record.get("Date", ""))[:10]] = int(record.get("No.", 0) or 0)

    matrix = sheets.get("Movement Matrix") or []
    if matrix:
        dates = [str(value or "")[:10] for value in matrix[0][1:]]
        for row in matrix[1:]:
            if not row or not row[0]:
                continue
            name = str(row[0]).strip()
            definition = find_movement_definition(name, dictionary)
            movement_id = definition.get("movement_id") if definition else ""
            key = movement_id or normalize_name(name)
            movement = database["movements"].setdefault(
                key,
                {
                    "movement_id": movement_id,
                    "name": name,
                    "aliases": [name],
                    "history": [],
                    "created_at": now_iso(),
                },
            )
            if definition:
                for alias in definition.get("aliases") or []:
                    if alias not in movement["aliases"]:
                        movement["aliases"].append(alias)
            for index, cell in enumerate(row[1:]):
                if not cell or index >= len(dates):
                    continue
                text = str(cell)
                order_match = re.search(r"(\d+)(?:st|nd|rd|th)\s+(?:work\s+)?movement", text, re.I)
                movement["history"].append(
                    {
                        "id": str(uuid.uuid4()),
                        "movement_id": movement_id,
                        "date": dates[index],
                        "training_day": day_by_date.get(dates[index]),
                        "order": int(order_match.group(1)) if order_match else None,
                        "sets": extract_load_blocks(text),
                        "raw": text,
                        "source": "fitness_tracker_clean_en.xlsx",
                    }
                )
    return database


def ensure_database() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        database = import_history() if HISTORY_FILE.exists() else blank_database()
        write_json(DATA_FILE, database)
    database = read_json(DATA_FILE, blank_database())
    dictionary = load_movement_dictionary()
    _, changed = migrate_movement_references(database, dictionary)
    if changed:
        backup_data()
        write_json(DATA_FILE, database)
    return database


def button(parent, text: str, command, kind: str = "secondary") -> tk.Button:
    palette = {
        "primary": (COLORS["orange"], COLORS["white"], "#B86C26"),
        "secondary": (COLORS["stone"], COLORS["ink"], "#D9D0C1"),
        "nav": (COLORS["navy"], "#D7DFEA", COLORS["navy_2"]),
        "teal": (COLORS["teal"], COLORS["white"], COLORS["teal_2"]),
        "danger": (COLORS["red"], COLORS["white"], "#8D3D37"),
    }
    background, foreground, active = palette[kind]
    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=background,
        fg=foreground,
        activebackground=active,
        activeforeground=foreground,
        relief="flat",
        bd=0,
        padx=15,
        pady=9,
        font=("Segoe UI", 9, "bold"),
        cursor="hand2",
    )


def apply_icon(window: tk.Misc) -> None:
    try:
        if ICON_FILE.exists():
            window.iconbitmap(str(ICON_FILE))
        if ICON_PNG.exists():
            image = tk.PhotoImage(file=str(ICON_PNG))
            window.iconphoto(True, image)
            window._fitness_icon = image
    except tk.TclError:
        pass


class FitnessTrackerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.movement_dictionary = load_movement_dictionary()
        self.movement_definitions_by_id, self.movement_definitions_by_alias = movement_definition_index(
            self.movement_dictionary
        )
        self.database = ensure_database()
        self.command_service = LedgerCommandService(
            DATA_FILE,
            MOVEMENT_DICTIONARY_FILE,
            BACKUP_DIR,
            self.parse_for_shared_service,
        )
        self.pending = None
        self.title("Fitness Ledger")
        self.geometry("1420x860+25+25")
        self.minsize(1120, 700)
        self.configure(bg=COLORS["cream"])
        apply_icon(self)
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self.configure_styles()
        self.pages = {}
        self.build()
        self.refresh_all()
        self.show_page("Quick Entry")
        self.protocol("WM_DELETE_WINDOW", self.close)

    def parse_for_shared_service(self, raw: str, database: dict, dictionary: dict) -> dict:
        current_dictionary = self.movement_dictionary
        current_by_id = self.movement_definitions_by_id
        current_by_alias = self.movement_definitions_by_alias
        try:
            self.movement_dictionary = dictionary
            self.movement_definitions_by_id, self.movement_definitions_by_alias = movement_definition_index(dictionary)
            return self.parse_entry(raw)
        finally:
            self.movement_dictionary = current_dictionary
            self.movement_definitions_by_id = current_by_id
            self.movement_definitions_by_alias = current_by_alias

    def configure_styles(self) -> None:
        self.style.configure(
            "Treeview",
            background=COLORS["paper"],
            fieldbackground=COLORS["paper"],
            foreground=COLORS["ink"],
            rowheight=34,
            font=("Microsoft YaHei UI", 9),
            borderwidth=0,
        )
        self.style.configure(
            "Treeview.Heading",
            background=COLORS["stone"],
            foreground=COLORS["muted"],
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padding=(7, 9),
        )
        self.style.map("Treeview", background=[("selected", "#DDEAE6")], foreground=[("selected", COLORS["navy"])])

    def build(self) -> None:
        self.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        sidebar = tk.Frame(self, bg=COLORS["navy"], width=220)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        tk.Label(sidebar, text="FL", bg=COLORS["navy"], fg=COLORS["orange"], font=("Georgia", 31, "bold")).pack(
            anchor="w", padx=24, pady=(28, 0)
        )
        tk.Label(sidebar, text="Fitness Ledger", bg=COLORS["navy"], fg=COLORS["white"], font=("Georgia", 18, "bold")).pack(
            anchor="w", padx=24, pady=(3, 2)
        )
        tk.Label(
            sidebar,
            text="BODY · FOOD · TRAINING",
            bg=COLORS["navy"],
            fg="#8FA0B8",
            font=("Segoe UI", 7, "bold"),
        ).pack(anchor="w", padx=24, pady=(0, 34))

        for name in ("Quick Entry", "Body", "Diet", "Training", "Movement Progress", "Data Check"):
            button(sidebar, name, lambda page=name: self.show_page(page), "nav").pack(fill="x", padx=14, pady=3)

        tk.Frame(sidebar, bg=COLORS["navy"]).pack(fill="both", expand=True)
        tk.Label(
            sidebar,
            text="Local data · automatic backups",
            bg=COLORS["navy"],
            fg="#71829A",
            font=("Segoe UI", 8),
        ).pack(anchor="w", padx=22, pady=20)

        self.content = tk.Frame(self, bg=COLORS["cream"])
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.rowconfigure(0, weight=1)
        self.content.columnconfigure(0, weight=1)

        self.build_quick_entry()
        self.build_body_page()
        self.build_diet_page()
        self.build_training_page()
        self.build_movement_page()
        self.build_data_check_page()

    def page_shell(self, name: str, title: str, subtitle: str) -> tk.Frame:
        page = tk.Frame(self.content, bg=COLORS["cream"])
        page.grid(row=0, column=0, sticky="nsew")
        page.rowconfigure(1, weight=1)
        page.columnconfigure(0, weight=1)
        header = tk.Frame(page, bg=COLORS["cream"])
        header.grid(row=0, column=0, sticky="ew", padx=32, pady=(26, 18))
        tk.Label(header, text=title, bg=COLORS["cream"], fg=COLORS["navy"], font=("Georgia", 25, "bold")).pack(anchor="w")
        tk.Label(header, text=subtitle, bg=COLORS["cream"], fg=COLORS["muted"], font=("Segoe UI", 10)).pack(
            anchor="w", pady=(4, 0)
        )
        self.pages[name] = page
        return page

    def build_quick_entry(self) -> None:
        page = self.page_shell(
            "Quick Entry",
            "Daily capture",
            "Paste one natural-language record. Review the parsed result before saving.",
        )
        body = tk.Frame(page, bg=COLORS["cream"])
        body.grid(row=1, column=0, sticky="nsew", padx=32, pady=(0, 25))
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=0)

        input_card = tk.Frame(body, bg=COLORS["paper"], highlightbackground=COLORS["stone"], highlightthickness=1)
        input_card.grid(row=0, column=0, sticky="nsew")
        input_card.rowconfigure(2, weight=1)
        input_card.columnconfigure(0, weight=1)
        tk.Label(input_card, text="RAW DAILY NOTE", bg=COLORS["paper"], fg=COLORS["teal"], font=("Segoe UI", 8, "bold")).grid(
            row=0, column=0, sticky="w", padx=24, pady=(22, 5)
        )
        tk.Label(
            input_card,
            text="Body data, meals, macros and training can be mixed in one entry.",
            bg=COLORS["paper"],
            fg=COLORS["navy"],
            font=("Georgia", 16, "bold"),
            wraplength=430,
            justify="left",
        ).grid(row=1, column=0, sticky="w", padx=24)
        self.raw_text = tk.Text(
            input_card,
            width=1,
            wrap="word",
            font=("Microsoft YaHei UI", 12),
            bg=COLORS["white"],
            fg=COLORS["ink"],
            insertbackground=COLORS["ink"],
            relief="flat",
            highlightbackground=COLORS["stone"],
            highlightcolor=COLORS["teal"],
            highlightthickness=1,
            padx=16,
            pady=14,
        )
        self.raw_text.grid(row=2, column=0, sticky="nsew", padx=24, pady=18)
        actions = tk.Frame(input_card, bg=COLORS["paper"])
        actions.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 22))
        actions.columnconfigure(0, weight=1)
        button(actions, "Parse & review", self.parse_and_review, "primary").grid(row=0, column=0, sticky="ew")
        button(actions, "Undo Last Save", self.undo_last_save, "danger").grid(row=0, column=1, padx=(10, 0))
        self.quick_status = tk.StringVar(value="Ready for a new daily entry.")
        tk.Label(
            input_card,
            textvariable=self.quick_status,
            bg=COLORS["paper"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
            wraplength=760,
        ).grid(row=4, column=0, sticky="w", padx=24, pady=(0, 18))

        side = tk.Frame(body, bg=COLORS["cream"], width=470)
        side.grid(row=0, column=1, sticky="nsew", padx=(18, 0))
        side.grid_propagate(False)
        side.rowconfigure(1, weight=1)
        side.columnconfigure(0, weight=1)

        status_card = tk.Frame(side, bg=COLORS["paper"], highlightbackground=COLORS["stone"], highlightthickness=1)
        status_card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        tk.Label(status_card, text="最近一天记录状态", bg=COLORS["paper"], fg=COLORS["teal"], font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=20, pady=(18, 5))
        self.today_status_title = tk.StringVar(value="尚无记录")
        tk.Label(status_card, textvariable=self.today_status_title, bg=COLORS["paper"], fg=COLORS["navy"], font=("Georgia", 16, "bold")).pack(anchor="w", padx=20)
        self.today_status_text = tk.StringVar(value="保存第一条记录后，这里会显示完整度。")
        tk.Label(status_card, textvariable=self.today_status_text, bg=COLORS["paper"], fg=COLORS["ink"], font=("Microsoft YaHei UI", 9), justify="left", wraplength=410).pack(anchor="w", fill="x", padx=20, pady=(8, 18))

        recent_card = tk.Frame(side, bg=COLORS["paper"], highlightbackground=COLORS["stone"], highlightthickness=1)
        recent_card.grid(row=1, column=0, sticky="nsew")
        recent_card.rowconfigure(1, weight=1)
        recent_card.columnconfigure(0, weight=1)
        tk.Label(recent_card, text="最近保存记录", bg=COLORS["paper"], fg=COLORS["navy"], font=("Georgia", 16, "bold")).grid(row=0, column=0, sticky="w", padx=20, pady=(18, 8))
        self.recent_records_frame = tk.Frame(recent_card, bg=COLORS["paper"])
        self.recent_records_frame.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        self.recent_records_frame.columnconfigure(0, weight=1)

    def build_table_with_scrollbars(
        self,
        parent: tk.Widget,
        columns: tuple[str, ...],
        headings: dict[str, str],
        *,
        horizontal: bool = True,
    ) -> ttk.Treeview:
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        tree = ttk.Treeview(parent, columns=columns, show="headings")
        for col in columns:
            tree.heading(col, text=headings[col])
            tree.column(col, width=120, anchor="w")
        tree.grid(row=0, column=0, sticky="nsew", padx=(18, 0), pady=(18, 4 if horizontal else 18))

        vertical = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        vertical.grid(row=0, column=1, sticky="ns", padx=(0, 18), pady=(18, 4 if horizontal else 18))
        tree.configure(yscrollcommand=vertical.set)

        if horizontal:
            horizontal_bar = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
            horizontal_bar.grid(row=1, column=0, sticky="ew", padx=(18, 0), pady=(0, 18))
            tree.configure(xscrollcommand=horizontal_bar.set)
        return tree

    def table_page(self, name: str, title: str, subtitle: str, columns: tuple[str, ...], headings: dict) -> ttk.Treeview:
        page = self.page_shell(name, title, subtitle)
        card = tk.Frame(page, bg=COLORS["paper"], highlightbackground=COLORS["stone"], highlightthickness=1)
        card.grid(row=1, column=0, sticky="nsew", padx=32, pady=(0, 25))
        return self.build_table_with_scrollbars(card, columns, headings)

    def build_body_page(self) -> None:
        columns = ("date", "weight", "bowel", "training", "cardio", "notes")
        headings = {
            "bowel": "排便记录",
            "date": "日期",
            "weight": "体重 kg",
            "context": "测量背景",
            "training": "训练",
            "cardio": "有氧",
            "notes": "备注",
        }
        self.body_table = self.table_page(
            "Body",
            "Body records",
            "Weight, measurement context, training and cardio are the primary daily view.",
            columns,
            headings,
        )
        self.body_table.column("date", width=135)
        self.body_table.column("weight", width=105)
        self.body_table.column("bowel", width=130)
        self.body_table.column("training", width=180)
        self.body_table.column("cardio", width=210)
        self.body_table.column("notes", width=360)
        self.body_records_by_item = {}
        self.body_table.bind("<Double-1>", self.open_selected_body_detail)

    def build_diet_page(self) -> None:
        columns = ("date", "calories", "protein", "carbs", "fat", "food", "notes")
        headings = {
            "date": "日期",
            "calories": "热量",
            "protein": "蛋白质",
            "carbs": "碳水",
            "fat": "脂肪",
            "food": "饮食摘要",
            "notes": "备注",
        }
        self.diet_table = self.table_page("Diet", "Diet records", "Newest days first, with macros kept as numeric values.", columns, headings)
        self.diet_table.column("date", width=120)
        self.diet_table.column("calories", width=90)
        self.diet_table.column("protein", width=95)
        self.diet_table.column("carbs", width=90)
        self.diet_table.column("fat", width=85)
        self.diet_table.column("food", width=420)
        self.diet_table.column("notes", width=260)
        self.diet_records_by_item = {}
        self.diet_table.bind("<Double-1>", self.open_selected_diet_detail)

    def build_training_page(self) -> None:
        columns = ("day", "date", "split", "summary", "notes")
        headings = {
            "day": "编号",
            "date": "日期",
            "split": "训练部位",
            "raw": "原始记录",
            "summary": "标准化摘要",
            "notes": "备注",
        }
        self.training_table = self.table_page(
            "Training",
            "Training sessions",
            "Original wording is preserved beside the structured movement interpretation.",
            columns,
            headings,
        )
        training_header = self.pages["Training"].grid_slaves(row=0, column=0)[0]
        button(training_header, "查看原始记录", self.open_selected_training_raw_detail, "secondary").pack(anchor="w", pady=(10, 0))
        self.training_table.column("day", width=70)
        self.training_table.column("date", width=120)
        self.training_table.column("split", width=170)
        self.training_table.column("summary", width=560)
        self.training_table.column("notes", width=210)
        self.training_records_by_item = {}
        self.training_table.bind("<Double-1>", self.open_selected_training_detail)

    def build_movement_page(self) -> None:
        page = self.page_shell(
            "Movement Progress",
            "Movement progress",
            "Existing movements stay on one row; new movements are added automatically.",
        )
        card = tk.Frame(page, bg=COLORS["paper"], highlightbackground=COLORS["stone"], highlightthickness=1)
        card.grid(row=1, column=0, sticky="nsew", padx=32, pady=(0, 25))
        card.rowconfigure(1, weight=1)
        card.columnconfigure(0, weight=1)
        controls = tk.Frame(card, bg=COLORS["paper"])
        controls.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 8))
        tk.Label(controls, text="Movement search", bg=COLORS["paper"], fg=COLORS["muted"], font=("Segoe UI", 8, "bold")).pack(
            side="left", padx=(0, 8)
        )
        self.movement_search = tk.StringVar()
        search = tk.Entry(
            controls,
            textvariable=self.movement_search,
            width=30,
            bg=COLORS["white"],
            fg=COLORS["ink"],
            relief="flat",
            highlightbackground=COLORS["stone"],
            highlightcolor=COLORS["teal"],
            highlightthickness=1,
            font=("Microsoft YaHei UI", 10),
        )
        search.pack(side="left", ipady=6)
        self.movement_search.trace_add("write", lambda *_: self.refresh_movements())
        button(controls, "Clear", lambda: self.movement_search.set(""), "secondary").pack(side="left", padx=7)
        button(controls, "动作词典管理", self.open_movement_dictionary_manager, "teal").pack(side="right")

        columns = ("movement",)
        self.movement_table = ttk.Treeview(card, columns=columns, show="headings")
        self.movement_table.heading("movement", text="动作")
        self.movement_table.column("movement", width=240, minwidth=220, stretch=False, anchor="w")
        self.movement_table.grid(row=1, column=0, sticky="nsew", padx=(20, 0), pady=(0, 4))
        vertical = ttk.Scrollbar(card, orient="vertical", command=self.movement_table.yview)
        horizontal = ttk.Scrollbar(card, orient="horizontal", command=self.movement_table.xview)
        self.movement_table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        vertical.grid(row=1, column=1, sticky="ns", padx=(0, 20), pady=(0, 4))
        horizontal.grid(row=2, column=0, sticky="ew", padx=(20, 0), pady=(0, 18))
        self.matrix_cell_detail_map = {}
        self.matrix_cell_records_map = {}
        self.movement_rows_by_item = {}
        self.movement_table.bind("<Double-1>", self.open_movement_cell_detail)

    def build_data_check_page(self) -> None:
        page = self.page_shell(
            "Data Check",
            "Data check",
            "Rule-based checks for missing, duplicated or suspicious records. This page never changes data.",
        )
        card = tk.Frame(page, bg=COLORS["paper"], highlightbackground=COLORS["stone"], highlightthickness=1)
        card.grid(row=1, column=0, sticky="nsew", padx=32, pady=(0, 25))
        card.rowconfigure(1, weight=1)
        card.columnconfigure(0, weight=1)
        controls = tk.Frame(card, bg=COLORS["paper"])
        controls.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 0))
        self.data_check_status = tk.StringVar(value="尚未检查。")
        tk.Label(
            controls,
            textvariable=self.data_check_status,
            bg=COLORS["paper"],
            fg=COLORS["muted"],
            font=("Microsoft YaHei UI", 9),
        ).pack(side="left")
        button(controls, "重新检查", self.refresh_data_check, "teal").pack(side="right")
        button(controls, "打开选中问题", self.open_selected_data_issue, "secondary").pack(side="right", padx=(0, 8))
        table_frame = tk.Frame(card, bg=COLORS["paper"])
        table_frame.grid(row=1, column=0, sticky="nsew")
        columns = ("severity", "date", "area", "issue", "action", "open")
        headings = {
            "severity": "严重程度",
            "date": "日期",
            "area": "区域",
            "issue": "问题",
            "action": "建议操作",
            "open": "Open",
        }
        self.data_check_table = self.build_table_with_scrollbars(table_frame, columns, headings)
        self.data_check_table.column("severity", width=90, stretch=False)
        self.data_check_table.column("date", width=120, stretch=False)
        self.data_check_table.column("area", width=130, stretch=False)
        self.data_check_table.column("issue", width=520)
        self.data_check_table.column("action", width=260)
        self.data_check_table.column("open", width=70, stretch=False, anchor="center")
        self.data_check_issues_by_item = {}
        self.data_check_table.bind("<Double-1>", lambda _event: self.open_selected_data_issue())

    def show_page(self, name: str) -> None:
        self.pages[name].tkraise()
        if name == "Data Check":
            self.refresh_data_check()

    def movement_definition(self, movement: dict) -> dict:
        movement_id = str(movement.get("movement_id", ""))
        definition = self.movement_definitions_by_id.get(movement_id)
        if definition:
            return definition
        candidates = [movement.get("name", ""), *(movement.get("aliases") or [])]
        for candidate in candidates:
            definition = self.movement_definitions_by_alias.get(normalize_name(str(candidate)))
            if definition:
                return definition
        return {}

    def resolve_movement(self, candidate: str) -> tuple[str, dict, bool]:
        normalized = normalize_name(candidate)
        definition = self.movement_definitions_by_alias.get(normalized)
        is_new = False
        if definition is None:
            definition = add_custom_movement_definition(candidate, self.movement_dictionary)
            self.movement_definitions_by_id, self.movement_definitions_by_alias = movement_definition_index(
                self.movement_dictionary
            )
            is_new = True
        movement_id = definition["movement_id"]
        for key, movement in self.database["movements"].items():
            if movement.get("movement_id") == movement_id:
                if candidate not in movement.setdefault("aliases", []):
                    movement["aliases"].append(candidate)
                return key, movement, is_new
        movement = {
            "movement_id": movement_id,
            "name": title_case_movement(candidate),
            "aliases": [candidate],
            "history": [],
            "created_at": now_iso(),
        }
        self.database["movements"][movement_id] = movement
        return movement_id, movement, True

    def review_new_movements(self, movements: list[dict], parent=None) -> set[str] | None:
        if any("_review_action" in movement for movement in movements):
            if any(movement.get("_review_action") == "cancel" for movement in movements):
                return None
            return {
                normalize_name(movement.get("name", ""))
                for movement in movements
                if movement.get("_review_action") == "add"
            }
        unknown = []
        seen = set()
        for movement in movements:
            name = str(movement.get("name", "")).strip()
            normalized = normalize_name(name)
            if not name or normalized in self.movement_definitions_by_alias or normalized in seen:
                continue
            seen.add(normalized)
            unknown.append(name)

        approved = set()
        for name in unknown:
            answer = messagebox.askyesnocancel(
                "发现新动作",
                f"动作词典中没有找到：\n\n{name}\n\n"
                "选择“是”将其加入动作词典和动作成长表。\n"
                "选择“否”将保留原始训练记录，但不加入动作成长表。\n"
                "选择“取消”将返回审核页面，本次不保存。",
                parent=parent or self,
            )
            if answer is None:
                return None
            if answer:
                approved.add(normalize_name(name))
        return approved

    def parse_training_movements(self, training_text: str) -> list[dict]:
        movements = []
        current = None
        pending_order = None

        def finish_current() -> None:
            nonlocal current
            if not current:
                return
            name = strip_movement_metrics(current["name"])
            if name:
                raw_detail = "\n".join(current["raw_lines"])
                definition = self.movement_definitions_by_alias.get(normalize_name(name), {})
                movements.append(
                    {
                        "order": current["order"],
                        "name": name,
                        "movement_id": definition.get("movement_id", ""),
                        "display_name": definition.get("display_name", name),
                        "sets": extract_load_blocks(raw_detail),
                        "cardio": {},
                        "raw": raw_detail,
                        "notes": "\n".join(current["notes"]),
                    }
                )
            current = None

        raw_lines = [line for line in str(training_text or "").splitlines() if line.strip()]
        for line_index, raw_line in enumerate(raw_lines):
            stripped = raw_line.strip()

            lower = stripped.lower()
            is_indented = raw_line[:1].isspace()
            note_match = re.match(r"^(notes?|澶囨敞)\s*[:锛歖\s*(.*)$", stripped, re.I)
            next_line = raw_lines[line_index + 1].strip() if line_index + 1 < len(raw_lines) else ""
            next_definition = self.movement_definitions_by_alias.get(normalize_name(next_line)) if next_line else None
            next_is_movement_header = bool(
                re.match(r"^(\d+)\s*(?:[.)]|[銆併€俔)\s*$", next_line)
                or re.match(r"^\s*(\d+)\s*(?:[.)]|[銆佢]\s*(?!\d)(.+)$", next_line)
                or next_definition is not None
                or extract_load_blocks(next_line)
            )
            if note_match and current and not is_indented and next_is_movement_header:
                is_indented = True
            if re.match(r"^(diet|饮食|cardio|有氧)\s*[:：]", lower) or (
                re.match(r"^(notes?|备注)\s*[:：]", lower) and not is_indented
            ):
                finish_current()
                break
            if re.match(r"^(diet|cardio)\s*[:：]", lower) or (re.match(r"^notes?\s*[:：]", lower) and not is_indented):
                finish_current()
                break

            number_only_match = re.match(r"^(\d+)\s*(?:[.)]|[、。])\s*$", stripped)
            if number_only_match:
                finish_current()
                pending_order = int(number_only_match.group(1))
                continue

            order_match = re.match(r"^\s*(\d+)\s*[\.\)、、]\s*(?!\d)(.+)$", stripped)
            fixed_order_match = re.match(r"^\s*(\d+)\s*(?:[.)]|[、。])\s*(?!\d)(.+)$", stripped)
            if fixed_order_match:
                finish_current()
                pending_order = None
                current = {
                    "order": int(fixed_order_match.group(1)),
                    "name": fixed_order_match.group(2).strip(),
                    "raw_lines": [stripped],
                    "notes": [],
                }
                continue
            if order_match:
                finish_current()
                pending_order = None
                current = {
                    "order": int(order_match.group(1)),
                    "name": order_match.group(2).strip(),
                    "raw_lines": [stripped],
                    "notes": [],
                }
                continue

            note_match = re.match(r"^(notes?|备注)\s*[:：]\s*(.*)$", stripped, re.I)
            next_line = raw_lines[line_index + 1].strip() if line_index + 1 < len(raw_lines) else ""
            definition = self.movement_definitions_by_alias.get(normalize_name(stripped))
            starts_unumbered_movement = (
                not note_match
                and not extract_load_blocks(stripped)
                and not is_cardio_line(stripped)
                and (definition is not None or bool(extract_load_blocks(next_line)))
            )
            if starts_unumbered_movement:
                finish_current()
                order = pending_order if pending_order is not None else len(movements) + 1
                pending_order = None
                current = {
                    "order": order,
                    "name": stripped,
                    "raw_lines": [stripped],
                    "notes": [],
                }
                continue

            if current:
                current["raw_lines"].append(stripped)
                if note_match:
                    current["notes"].append(note_match.group(2).strip())
                    continue
                continue

            if is_cardio_line(stripped):
                movements.append(
                    {
                        "order": len(movements) + 1,
                        "name": "Cardio",
                        "movement_id": "",
                        "display_name": "Cardio",
                        "sets": [],
                        "cardio": extract_cardio_metrics(stripped),
                        "raw": stripped,
                        "notes": "",
                    }
                )

        finish_current()
        return movements

    def parse_entry(self, raw: str) -> dict:
        entry_date = parse_date(raw)
        body = {
            "date": entry_date,
            "weight": parse_number(r"(?:体重|weight)\s*[:：]?\s*(\d+(?:\.\d+)?)", raw),
            "body_fat": parse_number(r"(?:体脂(?:率)?|body\s*fat)\s*[:：]?\s*(\d+(?:\.\d+)?)", raw),
            "waist": parse_number(r"(?:腰围|waist)\s*[:：]?\s*(\d+(?:\.\d+)?)", raw),
            "sleep": parse_number(r"(?:睡眠|sleep)\s*[:：]?\s*(\d+(?:\.\d+)?)", raw),
            "steps": parse_number(r"(?:步数|steps?)\s*[:：]?\s*(\d+(?:\.\d+)?)", raw),
            "context": "",
            "bowel_movement": extract_bowel_movement(raw),
            "training_summary": "",
            "cardio_summary": "",
            "notes": "",
        }
        if body["weight"] is None:
            body["weight"] = parse_number(r"(?:体重|weight)\s*[:：]?\s*(\d+(?:\.\d+)?)", raw)
        context_parts = []
        for phrase in ("早晨空腹", "晨起空腹", "晚上", "晚间", "参考值", "饭后"):
            if phrase in raw:
                context_parts.append(phrase)
        body["context"] = "；".join(context_parts)

        diet_section = ""
        diet_match = re.search(r"(?:饮食|diet)\s*[:：]?(.*?)(?=\n\s*(?:训练|training)\s*[:：]|$)", raw, re.I | re.S)
        if diet_match:
            diet_section = " ".join(line.strip() for line in diet_match.group(1).splitlines() if line.strip())
        diet = {
            "date": entry_date,
            "food_summary": diet_section,
            "calories": parse_number(r"(?:热量|卡路里|calories?|kcal)\s*[:：]?\s*(\d+(?:\.\d+)?)", raw),
            "protein": parse_number(r"(?:蛋白质|protein)\s*[:：]?\s*(\d+(?:\.\d+)?)", raw),
            "carbs": parse_number(r"(?:碳水(?:化合物)?|carbs?)\s*[:：]?\s*(\d+(?:\.\d+)?)", raw),
            "fat": parse_number(r"(?:脂肪|fat)\s*[:：]?\s*(\d+(?:\.\d+)?)", raw),
            "notes": "",
        }

        diet_after_training = re.search(
            r"(?ms)^\s*(?:diet|饮食)\s*[:：]\s*(.*?)(?=^\s*(?:notes?|备注|training|训练|cardio|有氧)\s*[:：]|\Z)",
            raw,
            re.I,
        )
        if diet_after_training:
            diet["food_summary"] = "\n".join(
                line.strip() for line in diet_after_training.group(1).splitlines() if line.strip()
            )
        global_notes = re.search(r"(?ms)^\s*(?:notes?|备注)\s*[:：]\s*(.*)$", raw, re.I)
        if global_notes:
            body["notes"] = global_notes.group(1).strip()
        modern_global_notes = re.search(r"(?ms)^(?:notes?|备注)\s*[:：]\s*(.*)$", raw, re.I)
        if modern_global_notes:
            body["notes"] = modern_global_notes.group(1).strip()
        split, training_text = extract_training_section(raw)
        body["training_summary"] = split
        cardio_section = extract_labeled_section(
            raw,
            ("cardio", "有氧"),
            ("diet", "饮食", "notes", "备注", "training", "训练"),
        )
        if cardio_section:
            body["cardio_summary"] = compact_section_lines(cardio_section)
        movement_lines = []
        for line in training_text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if re.match(r"^\d+\s*[.、)]", stripped) or extract_load_blocks(stripped) or is_cardio_line(stripped):
                movement_lines.append(stripped)

        movements = []
        for fallback_order, line in enumerate(movement_lines, 1):
            order_match = re.match(r"^\s*(\d+)\s*[.、)]", line)
            order = int(order_match.group(1)) if order_match else fallback_order
            if is_cardio_line(line):
                if re.search(r"跑步机|treadmill", line, re.I):
                    name = "跑步机"
                elif re.search(r"步行|快走|walk", line, re.I):
                    name = "步行"
                else:
                    name = "有氧"
            else:
                name = strip_movement_metrics(line)
            if not name:
                continue
            movements.append(
                {
                    "order": order,
                    "name": name,
                    "movement_id": (
                        self.movement_definitions_by_alias.get(normalize_name(name), {}).get("movement_id", "")
                    ),
                    "display_name": (
                        self.movement_definitions_by_alias.get(normalize_name(name), {}).get("display_name", name)
                    ),
                    "sets": extract_load_blocks(line),
                    "cardio": extract_cardio_metrics(line) if is_cardio_line(line) else {},
                    "raw": line,
                }
            )

        structured_movements = self.parse_training_movements(training_text)
        if structured_movements:
            movements = structured_movements

        return {
            "id": str(uuid.uuid4()),
            "date": entry_date,
            "raw": raw,
            "body": body,
            "diet": diet,
            "training": {"split": split, "raw": training_text, "movements": movements},
            "parsed_at": now_iso(),
        }

    def parse_and_review(self) -> None:
        raw = self.raw_text.get("1.0", "end").strip()
        if not raw:
            messagebox.showwarning("Empty entry", "Paste or type a daily record first.")
            return
        try:
            self.pending = self.command_service.parse(raw)["review"]
        except LedgerCommandError as exc:
            messagebox.showerror("Unable to parse", str(exc), parent=self)
            return
        training = self.pending["training"]
        training["standardized_summary"] = "；".join(
            f"第{movement['order']}个动作：{movement.get('display_name') or movement['name']}"
            for movement in training["movements"]
        )
        training["_initial_standardized_summary"] = training["standardized_summary"]
        training["_last_generated_standardized_summary"] = training["standardized_summary"]
        note_parts = []
        for movement in training["movements"]:
            note = str(movement.get("notes", "")).strip().rstrip("；;。.!！")
            if note:
                note_parts.append(f"{movement.get('display_name') or movement['name']}：{note}")
        training["notes"] = f"{'；'.join(note_parts)}。" if note_parts else ""
        training["_initial_notes"] = training["notes"]
        training["_last_generated_notes"] = training["notes"]
        self.open_review_window()

    def format_review_lines(self, parsed: dict) -> list[str]:
        body = parsed["body"]
        diet = parsed["diet"]
        training = parsed["training"]
        lines = [
            "Body",
            f"Weight: {body['weight'] if body['weight'] is not None else 'Not found'} kg",
            f"Bowel Movement: {body['bowel_movement'] or '-'}",
            f"Notes: {body['notes'] or '-'}",
            "",
            "Diet",
            f"Food: {diet['food_summary'] or 'Not found'}",
            f"Calories: {diet['calories'] if diet['calories'] is not None else 'Not found'} kcal",
            f"Protein: {diet['protein'] if diet['protein'] is not None else 'Not found'} g",
            f"Carbs: {diet['carbs'] if diet['carbs'] is not None else 'Not found'} g",
            f"Fat: {diet['fat'] if diet['fat'] is not None else 'Not found'} g",
            "",
            f"Training: {training['split'] or 'Not found'}",
        ]
        for movement in training["movements"]:
            lines.append("")
            is_new = not movement.get("movement_id")
            marker = "  [新动作，保存前需确认]" if is_new else ""
            lines.append(f"{movement['order']}. {movement.get('display_name') or movement['name']}{marker}")
            for item in movement["sets"]:
                lines.append(f"   {item['weight']:g}kg × {item['reps']} × {item['sets']}")
            if movement.get("notes"):
                lines.append(f"   Notes: {movement['notes']}")
            if not movement["sets"] and movement.get("cardio"):
                cardio = movement["cardio"]
                cardio_parts = []
                if cardio.get("duration_minutes") is not None:
                    cardio_parts.append(f"{cardio.get('duration_minutes'):g} min")
                if cardio.get("incline") is not None:
                    cardio_parts.append(f"incline {cardio.get('incline'):g}")
                if cardio.get("speed") is not None:
                    cardio_parts.append(f"speed {cardio.get('speed'):g}")
                if cardio.get("heart_rate") is not None:
                    cardio_parts.append(f"HR {cardio.get('heart_rate'):g}")
                lines.append(f"   {', '.join(cardio_parts) if cardio_parts else 'No set details found'}")
            elif not movement["sets"]:
                lines.append("   No set details found")
        if not training["movements"]:
            lines.append("No movements found")
        return lines

    def records_on_date(self, entry_date: str) -> dict[str, list[dict]]:
        target = str(entry_date)[:10]
        return {
            "body": [row for row in self.database["daily_records"] if str(row.get("Date", ""))[:10] == target],
            "diet": [row for row in self.database["diet_records"] if str(row.get("Date", ""))[:10] == target],
            "training": [row for row in self.database["training_sessions"] if str(row.get("Date", ""))[:10] == target],
        }

    def collect_review_warnings(self, parsed: dict) -> list[str]:
        body = parsed["body"]
        diet = parsed["diet"]
        training = parsed["training"]
        warnings = []
        if body.get("weight") is None:
            warnings.append("High · 缺少体重。")
        if not body.get("bowel_movement"):
            warnings.append("Medium · 缺少排便记录。")
        for field, label in (("calories", "热量"), ("protein", "蛋白质"), ("carbs", "碳水"), ("fat", "脂肪")):
            if diet.get(field) is None:
                warnings.append(f"High · 缺少{label}。")
        for movement in training.get("movements", []):
            if not movement.get("sets") and not movement.get("cardio"):
                warnings.append(f"Medium · 动作“{movement.get('name', '')}”没有识别到组数。")
            if not movement.get("movement_id"):
                warnings.append(f"Medium · 新动作“{movement.get('name', '')}”需要确认处理方式。")
        duplicates = self.records_on_date(parsed.get("date", ""))
        if any(duplicates.values()):
            warnings.append(
                "High · 同日期已有记录："
                f"Body {len(duplicates['body'])} / Diet {len(duplicates['diet'])} / Training {len(duplicates['training'])}。"
            )
        cardio = str(body.get("cardio_summary", "")).strip().lower()
        if cardio in {"none", "无", "否", "没有"} and re.search(r"跑步机|爬坡|有氧", parsed.get("raw", "")):
            warnings.append("Medium · Cardio 为 none，但原始文本其他位置出现了跑步机、爬坡或有氧。")
        if re.search(r"(?im)^\s*(?:notes?|备注)\s*[:：]", str(diet.get("food_summary", ""))):
            warnings.append("High · Food Summary 疑似混入了全局 notes。")
        if re.search(r"new movements?:|新动作提示|automatically registered", str(training.get("notes", "")), re.I):
            warnings.append("Medium · Training Notes 疑似包含系统生成的新动作提示。")
        return warnings

    @staticmethod
    def review_widget_value(widget: tk.Text) -> str:
        return widget.get("1.0", "end").strip()

    def apply_review_edits(self, show_errors: bool = True) -> bool:
        parsed = self.pending
        if not parsed or not hasattr(self, "review_widgets"):
            return True
        widgets = self.review_widgets
        entry_date = self.review_widget_value(widgets["date"])
        try:
            date.fromisoformat(entry_date)
        except ValueError:
            if show_errors:
                messagebox.showerror("日期无效", "日期必须使用 YYYY-MM-DD 格式。")
            return False

        numeric = (
            ("body", "weight", "体重"),
            ("diet", "calories", "热量"),
            ("diet", "protein", "蛋白质"),
            ("diet", "carbs", "碳水"),
            ("diet", "fat", "脂肪"),
        )
        for section, field, label in numeric:
            value = self.review_widget_value(widgets[section][field])
            try:
                parsed[section][field] = float(value) if value else None
            except ValueError:
                if show_errors:
                    messagebox.showerror("数值无效", f"{label}必须是数字或留空。")
                return False

        parsed["date"] = entry_date
        parsed["body"].update(
            {
                "date": entry_date,
                "bowel_movement": self.review_widget_value(widgets["body"]["bowel_movement"]),
                "training_summary": self.review_widget_value(widgets["body"]["training_summary"]),
                "cardio_summary": self.review_widget_value(widgets["body"]["cardio_summary"]),
                "notes": self.review_widget_value(widgets["body"]["notes"]),
            }
        )
        parsed["diet"].update(
            {
                "date": entry_date,
                "food_summary": self.review_widget_value(widgets["diet"]["food_summary"]),
                "notes": self.review_widget_value(widgets["diet"]["notes"]),
            }
        )
        parsed["training"]["split"] = self.review_widget_value(widgets["training"]["split"])
        summary_value = self.review_widget_value(widgets["training"]["standardized_summary"])
        notes_value = self.review_widget_value(widgets["training"]["notes"])

        action_codes = {
            "使用当前识别": "use",
            "加入动作词典": "add",
            "映射到已有动作": "map",
            "仅保留原始训练": "skip",
            "取消整次保存": "cancel",
            "Use current match": "use",
            "Add to dictionary": "add",
            "Map to existing movement": "map",
            "Keep raw training only": "skip",
            "Cancel whole save": "cancel",
        }
        for movement, controls in zip(parsed["training"]["movements"], self.review_movement_widgets):
            movement["display_name"] = controls["standard_name"].get().strip() or movement.get("name", "")
            movement["notes"] = self.review_widget_value(controls["notes"])
            movement["_review_action"] = action_codes.get(controls["action"].get(), "use")
            movement["_muscle_group"] = controls.get("group").get().strip() if controls.get("group") else ""
            selected = controls["mapping"].get().strip()
            movement["_mapped_movement_id"] = selected.split(" | ", 1)[0] if " | " in selected else ""
            if movement["_review_action"] == "map" and not movement["_mapped_movement_id"]:
                if show_errors:
                    messagebox.showerror("缺少映射", f"请为“{movement.get('name', '')}”选择一个已有动作。")
                return False
            if movement["_review_action"] == "add" and not movement["_muscle_group"]:
                if show_errors:
                    messagebox.showerror("缺少训练部位", f"请为新动作“{movement.get('name', '')}”选择训练部位。")
                return False
        active_movements = [
            movement
            for movement in parsed["training"]["movements"]
            if movement.get("_review_action") not in {"skip", "cancel"}
        ]
        generated_summary_parts = []
        generated_note_parts = []
        for movement in active_movements:
            display_name = movement.get("display_name") or movement.get("name", "")
            if movement.get("_review_action") == "map":
                definition = self.movement_definitions_by_id.get(movement.get("_mapped_movement_id", ""), {})
                display_name = definition.get("display_name") or display_name
            generated_summary_parts.append(f"第{movement.get('order')}个动作：{display_name}")
            note = str(movement.get("notes", "")).strip().rstrip("；;。.!！")
            if note:
                generated_note_parts.append(f"{display_name}：{note}")
        generated_summary_values = {
            parsed["training"].get("_initial_standardized_summary", ""),
            parsed["training"].get("_last_generated_standardized_summary", ""),
        }
        generated_note_values = {
            parsed["training"].get("_initial_notes", ""),
            parsed["training"].get("_last_generated_notes", ""),
        }
        if summary_value in generated_summary_values:
            summary_value = "；".join(generated_summary_parts)
            parsed["training"]["_last_generated_standardized_summary"] = summary_value
            widgets["training"]["standardized_summary"].delete("1.0", "end")
            widgets["training"]["standardized_summary"].insert("1.0", summary_value)
        if notes_value in generated_note_values:
            notes_value = f"{'；'.join(generated_note_parts)}。" if generated_note_parts else ""
            parsed["training"]["_last_generated_notes"] = notes_value
            widgets["training"]["notes"].delete("1.0", "end")
            widgets["training"]["notes"].insert("1.0", notes_value)
        parsed["training"]["standardized_summary"] = summary_value
        parsed["training"]["notes"] = notes_value
        return True

    def refresh_review_warnings(self) -> None:
        if not self.apply_review_edits(show_errors=False):
            return
        self.refresh_review_summary(apply_edits=False)
        warnings = self.collect_review_warnings(self.pending)
        self.review_warning_text.configure(state="normal")
        self.review_warning_text.delete("1.0", "end")
        self.review_warning_text.insert("1.0", "\n".join(warnings) if warnings else "未发现明显问题。")
        self.review_warning_text.configure(state="disabled")

    def format_review_summary(self, parsed: dict) -> str:
        body = parsed["body"]
        diet = parsed["diet"]
        training = parsed["training"]
        active_movements = [
            movement
            for movement in training.get("movements", [])
            if movement.get("_review_action") not in {"skip", "cancel"}
        ]
        new_count = sum(
            1
            for movement in active_movements
            if not movement.get("movement_id") and movement.get("_review_action") != "map"
        )

        def value_or_missing(value) -> str:
            return format_number(value) if value not in (None, "") else "缺失"

        notes_present = bool(str(body.get("notes", "")).strip() or str(training.get("notes", "")).strip())
        return (
            f"{parsed.get('date') or '日期缺失'}\n"
            f"体重：{value_or_missing(body.get('weight'))}    排便：{body.get('bowel_movement') or '缺失'}\n"
            f"热量：{value_or_missing(diet.get('calories'))} / 蛋白 {value_or_missing(diet.get('protein'))} / "
            f"碳水 {value_or_missing(diet.get('carbs'))} / 脂肪 {value_or_missing(diet.get('fat'))}\n"
            f"训练：{training.get('split') or body.get('training_summary') or '缺失'}    "
            f"动作数：{len(active_movements)}    新动作：{new_count}\n"
            f"有氧：{body.get('cardio_summary') or '缺失'}    备注：{'有' if notes_present else '无'}"
        )

    def refresh_review_summary(self, apply_edits: bool = True) -> None:
        if apply_edits and not self.apply_review_edits(show_errors=False):
            return
        if hasattr(self, "review_summary_var") and self.pending:
            self.review_summary_var.set(self.format_review_summary(self.pending))

    def confirm_review(self, window: tk.Toplevel) -> None:
        if not self.apply_review_edits():
            return
        if any(movement.get("_review_action") == "cancel" for movement in self.pending["training"]["movements"]):
            messagebox.showinfo("已取消", "动作处理方式选择了“取消整次保存”，本次没有写入数据。", parent=window)
            return
        self.commit_pending(window)

    def open_review_window(self) -> None:
        parsed = self.pending
        window = tk.Toplevel(self)
        window.title("Review parsed entry")
        window.geometry("1080x800")
        window.minsize(880, 650)
        window.configure(bg=COLORS["cream"])
        window.transient(self)
        window.grab_set()
        apply_icon(window)

        card = tk.Frame(window, bg=COLORS["paper"], highlightbackground=COLORS["stone"], highlightthickness=1)
        card.pack(fill="both", expand=True, padx=26, pady=26)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(3, weight=1)
        tk.Label(card, text="REVIEW BEFORE SAVE", bg=COLORS["paper"], fg=COLORS["teal"], font=("Segoe UI", 8, "bold")).pack(
            anchor="w", padx=26, pady=(22, 4)
        )
        tk.Label(card, text="保存前可直接修正字段；原始输入不会被改写。", bg=COLORS["paper"], fg=COLORS["navy"], font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w", padx=26)
        actions = tk.Frame(card, bg=COLORS["paper"])
        actions.pack(side="bottom", fill="x", padx=26, pady=(0, 22))
        button(actions, "Cancel", window.destroy, "secondary").pack(side="right", padx=(8, 0))
        button(actions, "Confirm & save", lambda: self.confirm_review(window), "primary").pack(side="right")
        button(actions, "Refresh warnings", self.refresh_review_warnings, "secondary").pack(side="left")

        summary_frame = tk.Frame(card, bg="#EDF5F2", highlightbackground="#C9DDD7", highlightthickness=1)
        summary_frame.pack(fill="x", padx=26, pady=(12, 2))
        tk.Label(summary_frame, text="最终摘要", bg="#EDF5F2", fg=COLORS["teal"], font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=12, pady=(9, 2))
        self.review_summary_var = tk.StringVar()
        tk.Label(summary_frame, textvariable=self.review_summary_var, bg="#EDF5F2", fg=COLORS["ink"], font=("Microsoft YaHei UI", 9), justify="left", anchor="w").pack(fill="x", padx=12, pady=(0, 9))

        warning_frame = tk.Frame(card, bg=COLORS["paper"])
        warning_frame.pack(fill="x", padx=26, pady=(12, 4))
        tk.Label(warning_frame, text="WARNINGS / 检查提示", bg=COLORS["paper"], fg=COLORS["red"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
        self.review_warning_text = tk.Text(warning_frame, height=5, wrap="word", bg="#FFF4E8", fg=COLORS["ink"], relief="flat", font=("Microsoft YaHei UI", 9), padx=10, pady=8)
        self.review_warning_text.pack(fill="x", pady=(5, 0))

        notebook = ttk.Notebook(card)
        notebook.pack(fill="both", expand=True, padx=26, pady=(8, 16))
        self.review_widgets = {"body": {}, "diet": {}, "training": {}}
        self.review_movement_widgets = []

        def build_form(title: str, section: str, fields: list[tuple[str, str, object, int]]) -> None:
            frame = tk.Frame(notebook, bg=COLORS["paper"])
            notebook.add(frame, text=title)
            frame.columnconfigure(1, weight=1)
            for row, (field, label, value, height) in enumerate(fields):
                tk.Label(frame, text=label, bg=COLORS["paper"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 9, "bold")).grid(row=row, column=0, sticky="nw", padx=18, pady=(12, 2))
                widget = tk.Text(frame, height=height, wrap="word", bg=COLORS["cream"], fg=COLORS["ink"], relief="flat", padx=8, pady=6)
                widget.grid(row=row, column=1, sticky="ew", padx=(0, 18), pady=(8, 2))
                widget.insert("1.0", "" if value is None else str(value))
                if field == "date":
                    self.review_widgets["date"] = widget
                else:
                    self.review_widgets[section][field] = widget

        body = parsed["body"]
        diet = parsed["diet"]
        training = parsed["training"]
        build_form("Body", "body", [
            ("date", "Date", parsed["date"], 1),
            ("weight", "Weight", body.get("weight"), 1),
            ("bowel_movement", "排便", body.get("bowel_movement"), 1),
            ("training_summary", "Training split", body.get("training_summary"), 1),
            ("cardio_summary", "Cardio", body.get("cardio_summary"), 2),
            ("notes", "Notes", body.get("notes"), 5),
        ])
        build_form("Diet", "diet", [
            ("calories", "Calories", diet.get("calories"), 1),
            ("protein", "Protein", diet.get("protein"), 1),
            ("carbs", "Carbs", diet.get("carbs"), 1),
            ("fat", "Fat", diet.get("fat"), 1),
            ("food_summary", "Food Summary", diet.get("food_summary"), 8),
            ("notes", "Notes", diet.get("notes"), 3),
        ])
        build_form("Training", "training", [
            ("split", "Split", training.get("split"), 1),
            ("standardized_summary", "Standardized Summary", training.get("standardized_summary"), 4),
            ("notes", "Training Notes", training.get("notes"), 5),
        ])

        movement_outer = tk.Frame(notebook, bg=COLORS["paper"])
        notebook.add(movement_outer, text="Movements")
        movement_outer.rowconfigure(0, weight=1)
        movement_outer.columnconfigure(0, weight=1)
        canvas = tk.Canvas(movement_outer, bg=COLORS["paper"], highlightthickness=0)
        scroll = ttk.Scrollbar(movement_outer, orient="vertical", command=canvas.yview)
        movement_frame = tk.Frame(canvas, bg=COLORS["paper"])
        movement_frame.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=movement_frame, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        mapping_values = [
            f"{definition['movement_id']} | {definition.get('display_name', '')}"
            for definition in self.movement_dictionary.get("movements", [])
            if definition.get("movement_id") and definition.get("active", True)
        ]
        for row, movement in enumerate(training["movements"]):
            box = tk.Frame(movement_frame, bg=COLORS["cream"], highlightbackground=COLORS["stone"], highlightthickness=1)
            box.grid(row=row, column=0, sticky="ew", padx=12, pady=8)
            movement_frame.columnconfigure(0, weight=1)
            box.columnconfigure(1, weight=1)
            original = movement.get("name", "")
            movement_id = movement.get("movement_id", "")
            sets_text = ", ".join(f"{item['weight']:g}kg × {item['reps']} × {item['sets']}" for item in movement.get("sets", [])) or "未识别组数"
            tk.Label(box, text=f"{movement.get('order')}. 原始动作：{original}", bg=COLORS["cream"], fg=COLORS["navy"], font=("Microsoft YaHei UI", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 4))
            tk.Label(box, text=f"movement_id: {movement_id or 'NEW'}\nsets: {sets_text}", bg=COLORS["cream"], fg=COLORS["muted"], justify="left").grid(row=1, column=0, sticky="nw", padx=12)
            standard_name = tk.Entry(box, bg=COLORS["white"], fg=COLORS["ink"], relief="flat")
            standard_name.grid(row=1, column=1, sticky="ew", padx=(4, 12), pady=2)
            standard_name.insert(0, movement.get("display_name") or original)
            notes_widget = tk.Text(box, height=2, wrap="word", bg=COLORS["white"], fg=COLORS["ink"], relief="flat")
            notes_widget.grid(row=2, column=1, sticky="ew", padx=(4, 12), pady=4)
            notes_widget.insert("1.0", movement.get("notes", ""))
            tk.Label(box, text="动作备注", bg=COLORS["cream"], fg=COLORS["muted"]).grid(row=2, column=0, sticky="nw", padx=12, pady=4)
            action_values = ["使用当前识别", "映射到已有动作", "仅保留原始训练", "取消整次保存"] if movement_id else ["加入动作词典", "映射到已有动作", "仅保留原始训练", "取消整次保存"]
            action = ttk.Combobox(box, values=action_values, state="readonly", width=22)
            action.set(action_values[0])
            action.grid(row=3, column=0, sticky="w", padx=12, pady=(4, 10))
            mapping = ttk.Combobox(box, values=mapping_values, state="readonly", width=42)
            if movement_id:
                current = next((value for value in mapping_values if value.startswith(f"{movement_id} | ")), "")
                mapping.set(current)
            mapping.grid(row=3, column=1, sticky="ew", padx=(4, 12), pady=(4, 10))
            self.review_movement_widgets.append({"standard_name": standard_name, "notes": notes_widget, "action": action, "mapping": mapping})

        for section_widgets in self.review_widgets.values():
            if isinstance(section_widgets, dict):
                for widget in section_widgets.values():
                    widget.bind("<KeyRelease>", lambda _event: self.after_idle(self.refresh_review_summary))
        self.review_widgets["date"].bind("<KeyRelease>", lambda _event: self.after_idle(self.refresh_review_summary))
        for controls in self.review_movement_widgets:
            controls["standard_name"].bind("<KeyRelease>", lambda _event: self.after_idle(self.refresh_review_summary))
            controls["notes"].bind("<KeyRelease>", lambda _event: self.after_idle(self.refresh_review_summary))
            controls["action"].bind("<<ComboboxSelected>>", lambda _event: self.after_idle(self.refresh_review_summary))
            controls["mapping"].bind("<<ComboboxSelected>>", lambda _event: self.after_idle(self.refresh_review_summary))
        self.refresh_review_warnings()

    def choose_duplicate_action(self, entry_date: str, duplicates: dict[str, list[dict]], parent) -> str | None:
        result = {"value": None}
        window = tk.Toplevel(self)
        window.title("重复日期处理")
        window.geometry("560x360")
        window.resizable(False, False)
        window.configure(bg=COLORS["cream"])
        window.transient(parent)
        window.grab_set()
        apply_icon(window)
        card = tk.Frame(window, bg=COLORS["paper"], highlightbackground=COLORS["stone"], highlightthickness=1)
        card.pack(fill="both", expand=True, padx=24, pady=24)
        tk.Label(card, text="检测到同日期记录", bg=COLORS["paper"], fg=COLORS["navy"], font=("Georgia", 20, "bold")).pack(anchor="w", padx=22, pady=(22, 6))
        tk.Label(
            card,
            text=f"{entry_date}\nBody {len(duplicates['body'])} 条 · Diet {len(duplicates['diet'])} 条 · Training {len(duplicates['training'])} 条",
            bg=COLORS["paper"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 10), justify="left",
        ).pack(anchor="w", padx=22, pady=(0, 18))

        def choose(value: str | None) -> None:
            result["value"] = value
            window.destroy()

        button(card, "覆盖当天主记录", lambda: choose("overwrite"), "danger").pack(fill="x", padx=22, pady=4)
        button(card, "追加为同一天第二条训练", lambda: choose("append_training"), "teal").pack(fill="x", padx=22, pady=4)
        button(card, "取消保存", lambda: choose(None), "secondary").pack(fill="x", padx=22, pady=4)
        window.protocol("WM_DELETE_WINDOW", lambda: choose(None))
        self.wait_window(window)
        return result["value"]

    def remove_records_for_overwrite(self, entry_date: str, replacement_id: str) -> int | None:
        target = str(entry_date)[:10]
        removed_sessions = [
            row for row in self.database["training_sessions"] if str(row.get("Date", ""))[:10] == target
        ]
        removed_days = {
            int(row.get("No."))
            for row in removed_sessions
            if str(row.get("No.", "")).strip().isdigit()
        }
        self.database["daily_records"] = [
            row for row in self.database["daily_records"] if str(row.get("Date", ""))[:10] != target
        ]
        self.database["diet_records"] = [
            row for row in self.database["diet_records"] if str(row.get("Date", ""))[:10] != target
        ]
        self.database["training_sessions"] = [
            row for row in self.database["training_sessions"] if str(row.get("Date", ""))[:10] != target
        ]
        for movement in self.database["movements"].values():
            movement["history"] = [
                history
                for history in movement.get("history", [])
                if str(history.get("date", ""))[:10] != target
            ]
        for raw_record in self.database["raw_entries"]:
            if str(raw_record.get("date", ""))[:10] == target and not raw_record.get("superseded"):
                raw_record["superseded"] = True
                raw_record["superseded_at"] = now_iso()
                raw_record["superseded_by"] = replacement_id
        return min(removed_days) if removed_days else None

    def tracker_movement_for_definition(self, definition: dict, candidate: str) -> tuple[str, dict]:
        movement_id = definition["movement_id"]
        for key, movement in self.database["movements"].items():
            if movement.get("movement_id") == movement_id:
                if candidate and candidate not in movement.setdefault("aliases", []):
                    movement["aliases"].append(candidate)
                return key, movement
        movement = {
            "movement_id": movement_id,
            "name": definition.get("display_name") or title_case_movement(candidate),
            "aliases": [candidate] if candidate else [],
            "history": [],
            "created_at": now_iso(),
        }
        self.database["movements"][movement_id] = movement
        return movement_id, movement

    def resolve_reviewed_movement(self, movement_data: dict) -> tuple[str, dict] | None:
        action = movement_data.get("_review_action", "use")
        candidate = movement_data.get("name", "")
        if action == "skip":
            return None
        if action == "map":
            definition = self.movement_definitions_by_id.get(movement_data.get("_mapped_movement_id", ""))
            if not definition:
                return None
            aliases = definition.setdefault("aliases", [])
            if candidate and candidate not in aliases:
                aliases.append(candidate)
                write_json(MOVEMENT_DICTIONARY_FILE, self.movement_dictionary)
                self.movement_definitions_by_id, self.movement_definitions_by_alias = movement_definition_index(
                    self.movement_dictionary
                )
            return self.tracker_movement_for_definition(definition, candidate)
        if action == "add" and normalize_name(candidate) not in self.movement_definitions_by_alias:
            standard_name = movement_data.get("display_name") or candidate
            definition = add_custom_movement_definition(standard_name, self.movement_dictionary)
            definition["muscle_group"] = str(movement_data.get("_muscle_group") or "Unclassified")
            if candidate and candidate not in definition.setdefault("aliases", []):
                definition["aliases"].append(candidate)
                write_json(MOVEMENT_DICTIONARY_FILE, self.movement_dictionary)
            self.movement_definitions_by_id, self.movement_definitions_by_alias = movement_definition_index(
                self.movement_dictionary
            )
            return self.tracker_movement_for_definition(definition, candidate)
        key, movement, _is_new = self.resolve_movement(candidate)
        return key, movement

    def _legacy_commit_pending(self, window: tk.Toplevel) -> None:
        parsed = self.pending
        approved_new_movements = self.review_new_movements(parsed["training"]["movements"], window)
        if approved_new_movements is None:
            return
        entry_date = parsed["date"]
        duplicates = self.records_on_date(entry_date)
        save_mode = "normal"
        replacement_day = None
        if any(duplicates.values()):
            save_mode = self.choose_duplicate_action(entry_date, duplicates, window)
            if save_mode is None:
                return
        tracker_checkpoint, _dictionary_checkpoint = create_undo_checkpoint()
        if tracker_checkpoint is None:
            messagebox.showerror("无法保存", "未能创建保存前检查点，数据未写入。", parent=window)
            return
        if save_mode == "overwrite":
            replacement_day = self.remove_records_for_overwrite(entry_date, parsed["id"])
        raw_record = {
            "id": parsed["id"],
            "date": entry_date,
            "text": parsed["raw"],
            "created_at": now_iso(),
            "save_mode": save_mode,
        }
        self.database["raw_entries"].append(raw_record)

        body = parsed["body"]
        save_primary_records = save_mode != "append_training"
        if save_primary_records and any(
            body.get(field) not in (None, "")
            for field in ("weight", "body_fat", "waist", "sleep", "steps", "bowel_movement", "training_summary", "cardio_summary", "notes")
        ):
            body_record = {
                "id": str(uuid.uuid4()),
                "Date": entry_date,
                "Weight (kg)": body["weight"],
                "Body Fat %": body["body_fat"],
                "Waist (cm)": body["waist"],
                "Sleep (h)": body["sleep"],
                "Steps": body["steps"],
                "Context": body["context"],
                "Bowel Movement": body["bowel_movement"],
                "Training": body["training_summary"],
                "Cardio": body["cardio_summary"],
                "Notes": body["notes"],
                "source": "text entry",
            }
            self.database["daily_records"].append(body_record)

        diet = parsed["diet"]
        if save_primary_records and (diet["food_summary"] or any(diet.get(field) is not None for field in ("calories", "protein", "carbs", "fat"))):
            self.database["diet_records"].append(
                {
                    "id": str(uuid.uuid4()),
                    "Date": entry_date,
                    "Food Summary": diet["food_summary"],
                    "Calories (kcal)": diet["calories"],
                    "Protein (g)": diet["protein"],
                    "Carbs (g)": diet["carbs"],
                    "Fat (g)": diet["fat"],
                    "Notes": diet["notes"],
                    "source": "text entry",
                }
            )

        training = parsed["training"]
        if training["split"] or training["movements"]:
            existing_days = [int(row.get("No.") or 0) for row in self.database["training_sessions"]]
            day_number = replacement_day or (max(existing_days, default=0) + 1)
            summary_parts = []
            movement_note_parts = []
            skipped_movements = []
            for movement_data in training["movements"]:
                normalized_name = normalize_name(movement_data["name"])
                is_known = normalized_name in self.movement_definitions_by_alias
                review_action = movement_data.get("_review_action", "use")
                if review_action == "skip" or (
                    not is_known
                    and review_action not in {"add", "map"}
                    and normalized_name not in approved_new_movements
                ):
                    skipped_movements.append(movement_data["name"])
                    continue
                resolved = self.resolve_reviewed_movement(movement_data)
                if resolved is None:
                    skipped_movements.append(movement_data["name"])
                    continue
                key, movement = resolved
                history = {
                    "id": str(uuid.uuid4()),
                    "movement_id": movement.get("movement_id", ""),
                    "date": entry_date,
                    "training_day": day_number,
                    "order": movement_data["order"],
                    "sets": movement_data["sets"],
                    "cardio": movement_data.get("cardio") or {},
                    "raw": movement_data["raw"],
                    "notes": movement_data.get("notes", ""),
                    "source": "text entry",
                }
                movement["history"].append(history)
                definition = self.movement_definitions_by_id.get(movement.get("movement_id", ""), {})
                display_name = movement_data.get("display_name") or definition.get("display_name") or movement["name"]
                summary_parts.append(f"第{movement_data['order']}个动作：{display_name}")
                movement_notes = str(movement_data.get("notes", "")).strip()
                if movement_notes:
                    movement_note_parts.append(f"{display_name}：{movement_notes.rstrip('；;。.!！')}")
            training_notes = training.get("notes", "")
            if save_mode == "append_training":
                marker = "同日追加训练。"
                training_notes = f"{marker}{training_notes}" if training_notes else marker
            self.database["training_sessions"].append(
                {
                    "id": str(uuid.uuid4()),
                    "No.": day_number,
                    "Date": entry_date,
                    "Split": training["split"],
                    "Raw Record": training["raw"],
                    "Standardized Summary": training.get("standardized_summary") or "；".join(summary_parts),
                    "Notes": training_notes or (f"{'；'.join(movement_note_parts)}。" if movement_note_parts else ""),
                    "save_mode": save_mode,
                    "source": "text entry",
                }
            )
            if skipped_movements:
                raw_record["skipped_movements"] = skipped_movements

        write_json(DATA_FILE, self.database)
        self.raw_text.delete("1.0", "end")
        self.quick_status.set(f"Saved {entry_date}. All views have been refreshed.")
        self.pending = None
        window.destroy()
        self.refresh_all()
        messagebox.showinfo("Saved", f"Daily record for {entry_date} was saved.")

    def commit_pending(self, window: tk.Toplevel) -> None:
        parsed = self.pending
        entry_date = parsed["date"]
        duplicates = self.records_on_date(entry_date)
        save_mode = "normal"
        if any(duplicates.values()):
            save_mode = self.choose_duplicate_action(entry_date, duplicates, window)
            if save_mode is None:
                return
        try:
            self.command_service.save(parsed, save_mode)
        except LedgerCommandError as exc:
            messagebox.showerror("Unable to save", str(exc), parent=window)
            return
        except Exception as exc:
            messagebox.showerror("Unable to save", f"The original files were preserved.\n\n{exc}", parent=window)
            return
        self.database = read_json(DATA_FILE, blank_database())
        self.movement_dictionary = load_movement_dictionary()
        self.movement_definitions_by_id, self.movement_definitions_by_alias = movement_definition_index(
            self.movement_dictionary
        )
        self.raw_text.delete("1.0", "end")
        self.quick_status.set(f"Saved {entry_date}. All views have been refreshed.")
        self.pending = None
        window.destroy()
        self.refresh_all()
        messagebox.showinfo("Saved", f"Daily record for {entry_date} was saved.")

    def refresh_all(self) -> None:
        self.refresh_body()
        self.refresh_diet()
        self.refresh_training()
        self.refresh_movements()
        if hasattr(self, "data_check_table"):
            self.refresh_data_check()
        if hasattr(self, "recent_records_frame"):
            self.refresh_quick_overview()

    def recent_record_dates(self, limit: int = 3) -> list[str]:
        dates = {
            str(record.get("Date", ""))[:10]
            for collection in (
                self.database.get("daily_records", []),
                self.database.get("diet_records", []),
                self.database.get("training_sessions", []),
            )
            for record in collection
            if record.get("Date")
        }
        dates.update(
            str(record.get("date", ""))[:10]
            for record in self.database.get("raw_entries", [])
            if record.get("date")
        )
        return sorted((day for day in dates if day), reverse=True)[:limit]

    def raw_records_on_date(self, entry_date: str) -> list[dict]:
        target = str(entry_date)[:10]
        return sorted(
            [record for record in self.database.get("raw_entries", []) if str(record.get("date", ""))[:10] == target],
            key=lambda record: str(record.get("created_at", "")),
            reverse=True,
        )

    def open_record_from_overview(self, record_type: str, record: dict | None) -> None:
        if not record:
            return
        record_id = str(record.get("id", ""))
        record_maps = {
            "body": self.body_records_by_item,
            "diet": self.diet_records_by_item,
            "training": self.training_records_by_item,
        }
        record_maps[record_type][record_id] = record
        self.open_record_editor(record_type, record_id)

    def open_raw_record_detail(self, raw_record: dict | None) -> None:
        if not raw_record:
            return
        title = f"原始输入 {str(raw_record.get('date', ''))[:10]}"
        self.open_detail_window(title, raw_record.get("text", "") or "-")

    def latest_day_status(self, entry_date: str) -> tuple[str, str]:
        grouped = self.records_on_date(entry_date)
        body = grouped["body"][-1] if grouped["body"] else {}
        diet = grouped["diet"][-1] if grouped["diet"] else {}
        trainings = grouped["training"]
        raw_records = self.raw_records_on_date(entry_date)
        raw_text = "\n".join(str(record.get("text", "")) for record in raw_records)
        weight_status = "✓" if body.get("Weight (kg)") not in (None, "") else "缺失"
        bowel_status = "✓" if str(body.get("Bowel Movement", "")).strip() else "缺失"
        macros_complete = all(
            diet.get(field) not in (None, "")
            for field in ("Calories (kcal)", "Protein (g)", "Carbs (g)", "Fat (g)")
        )
        macro_status = "✓" if macros_complete else "缺失"
        diet_status = "✓" if str(diet.get("Food Summary", "")).strip() else "缺失"
        training_status = f"✓ ({len(trainings)}次)" if trainings else "缺失"
        cardio = str(body.get("Cardio", "")).strip()
        normalized_cardio = cardio.lower()
        if normalized_cardio in {"none", "无", "否", "没有", "无有氧"}:
            cardio_status = "无有氧"
        elif cardio:
            cardio_status = "✓"
        elif re.search(r"跑步机|爬坡|有氧", raw_text):
            cardio_status = "可能缺失"
        else:
            cardio_status = "缺失"
        new_movement_ids = {
            history.get("movement_id") or movement.get("movement_id")
            for movement in self.database.get("movements", {}).values()
            for history in movement.get("history", [])
            if str(history.get("date", ""))[:10] == entry_date
            and str(history.get("movement_id") or movement.get("movement_id", "")).startswith("CUSTOM_")
        }
        high_count = sum(
            1
            for issue in self.collect_data_issues()
            if issue.get("severity") == "High" and issue.get("date") == entry_date
        )
        status = (
            f"体重 {weight_status}   排便 {bowel_status}\n"
            f"营养 {macro_status}   饮食 {diet_status}\n"
            f"训练 {training_status}   有氧 {cardio_status}\n"
            f"新动作 {len(new_movement_ids)}个   High 问题 {high_count}个"
        )
        return entry_date, status

    def refresh_quick_overview(self) -> None:
        dates = self.recent_record_dates(3)
        if dates:
            title, status = self.latest_day_status(dates[0])
            self.today_status_title.set(title)
            self.today_status_text.set(status)
        else:
            self.today_status_title.set("尚无记录")
            self.today_status_text.set("保存第一条记录后，这里会显示完整度。")
        for child in self.recent_records_frame.winfo_children():
            child.destroy()
        if not dates:
            tk.Label(self.recent_records_frame, text="暂无保存记录", bg=COLORS["paper"], fg=COLORS["muted"]).grid(row=0, column=0, sticky="w", padx=6, pady=8)
            return

        def small_button(parent, text, command, enabled=True):
            widget = tk.Button(
                parent,
                text=text,
                command=command,
                bg=COLORS["stone"],
                fg=COLORS["ink"],
                activebackground="#D9D0C1",
                relief="flat",
                bd=0,
                padx=7,
                pady=5,
                font=("Microsoft YaHei UI", 8),
                cursor="hand2" if enabled else "arrow",
                state="normal" if enabled else "disabled",
            )
            return widget

        for row, day in enumerate(dates):
            grouped = self.records_on_date(day)
            body_record = grouped["body"][-1] if grouped["body"] else None
            diet_record = grouped["diet"][-1] if grouped["diet"] else None
            training_record = grouped["training"][-1] if grouped["training"] else None
            raw_records = self.raw_records_on_date(day)
            raw_record = next((record for record in raw_records if not record.get("superseded")), raw_records[0] if raw_records else None)
            weight = body_record.get("Weight (kg)") if body_record else None
            split = training_record.get("Split", "") if training_record else "无训练"
            calories = diet_record.get("Calories (kcal)") if diet_record else None
            block = tk.Frame(self.recent_records_frame, bg=COLORS["cream"], highlightbackground=COLORS["stone"], highlightthickness=1)
            block.grid(row=row, column=0, sticky="ew", padx=5, pady=5)
            block.columnconfigure(0, weight=1)
            summary = f"{day}  |  体重 {format_number(weight) or '-'}  |  {split or '-'}  |  热量 {format_number(calories) or '-'}"
            tk.Label(block, text=summary, bg=COLORS["cream"], fg=COLORS["navy"], font=("Microsoft YaHei UI", 9, "bold"), anchor="w", wraplength=410).grid(row=0, column=0, sticky="ew", padx=10, pady=(9, 5))
            actions = tk.Frame(block, bg=COLORS["cream"])
            actions.grid(row=1, column=0, sticky="w", padx=8, pady=(0, 8))
            small_button(actions, "Body", lambda record=body_record: self.open_record_from_overview("body", record), body_record is not None).pack(side="left", padx=2)
            small_button(actions, "Diet", lambda record=diet_record: self.open_record_from_overview("diet", record), diet_record is not None).pack(side="left", padx=2)
            small_button(actions, "Training", lambda record=training_record: self.open_record_from_overview("training", record), training_record is not None).pack(side="left", padx=2)
            small_button(actions, "原始输入", lambda record=raw_record: self.open_raw_record_detail(record), raw_record is not None).pack(side="left", padx=2)
            small_button(actions, "Undo", self.undo_last_save, True).pack(side="left", padx=2)

    def undo_last_save(self) -> None:
        checkpoints = sorted(BACKUP_DIR.glob("undo_tracker_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        if not checkpoints:
            messagebox.showinfo("Undo Last Save", "没有可撤销的保存记录。")
            return
        tracker_checkpoint = checkpoints[0]
        suffix = tracker_checkpoint.name[len("undo_tracker_") :]
        dictionary_checkpoint = BACKUP_DIR / f"undo_dictionary_{suffix}"
        try:
            restored_database = read_json(tracker_checkpoint, None)
            restored_dictionary = read_json(dictionary_checkpoint, None) if dictionary_checkpoint.exists() else None
            if not isinstance(restored_database, dict):
                raise ValueError("数据库检查点无效")
        except Exception as exc:
            messagebox.showerror("Undo Last Save", f"无法读取撤销检查点：{exc}")
            return
        if not messagebox.askyesno(
            "Undo Last Save",
            "确定要撤销最近一次保存吗？\n\n当前数据将恢复到上一次保存前。",
        ):
            return
        backup_data("pre_undo_tracker")
        backup_file(MOVEMENT_DICTIONARY_FILE, "pre_undo_dictionary")
        write_json(DATA_FILE, restored_database)
        if isinstance(restored_dictionary, dict):
            write_json(MOVEMENT_DICTIONARY_FILE, restored_dictionary)
        tracker_checkpoint.rename(tracker_checkpoint.with_name(tracker_checkpoint.name.replace("undo_tracker_", "undone_tracker_", 1)))
        if dictionary_checkpoint.exists():
            dictionary_checkpoint.rename(
                dictionary_checkpoint.with_name(dictionary_checkpoint.name.replace("undo_dictionary_", "undone_dictionary_", 1))
            )
        self.database = restored_database
        self.movement_dictionary = load_movement_dictionary()
        self.movement_definitions_by_id, self.movement_definitions_by_alias = movement_definition_index(
            self.movement_dictionary
        )
        self.pending = None
        self.refresh_all()
        self.quick_status.set("最近一次保存已撤销。")
        messagebox.showinfo("Undo Last Save", "已恢复到最近一次保存前的状态。")

    @staticmethod
    def date_counts(records: list[dict], field: str = "Date") -> dict[str, int]:
        counts = {}
        for record in records:
            value = str(record.get(field, ""))[:10]
            if value:
                counts[value] = counts.get(value, 0) + 1
        return counts

    def collect_data_issues(self) -> list[dict]:
        issues = []

        def add(
            severity: str,
            day: str,
            area: str,
            issue: str,
            action: str,
            target_type: str = "",
            target_id: str = "",
            movement_id: str = "",
        ) -> None:
            issues.append(
                {
                    "severity": severity,
                    "date": day,
                    "area": area,
                    "issue": issue,
                    "action": action,
                    "target_type": target_type,
                    "target_id": target_id,
                    "movement_id": movement_id,
                }
            )

        for record in self.database.get("daily_records", []):
            day = str(record.get("Date", ""))[:10]
            if record.get("Weight (kg)") in (None, ""):
                add("High", day, "Body", "缺少体重。", "打开 Body 记录编辑", "body", str(record.get("id", "")))
            if len(str(record.get("Training", ""))) > 100:
                add("High", day, "Body", "Training 字段过长，疑似混入完整训练记录。", "打开 Body 记录编辑", "body", str(record.get("id", "")))
            if len(str(record.get("Cardio", ""))) > 100:
                add("High", day, "Body", "Cardio 字段过长，疑似混入完整输入。", "打开 Body 记录编辑", "body", str(record.get("id", "")))
            notes = str(record.get("Notes", ""))
            if len(notes) > 600 or re.search(r"(?im)^(?:training|diet|cardio)\s*[:：]", notes):
                add("High", day, "Body", "Notes 疑似混入 diet/training 全文。", "打开 Body 记录编辑", "body", str(record.get("id", "")))

        for record in self.database.get("diet_records", []):
            day = str(record.get("Date", ""))[:10]
            for field, label in (("Calories (kcal)", "热量"), ("Protein (g)", "蛋白质"), ("Carbs (g)", "碳水"), ("Fat (g)", "脂肪")):
                if record.get(field) in (None, ""):
                    add("High", day, "Diet", f"缺少{label}。", "打开 Diet 记录编辑", "diet", str(record.get("id", "")))
            if re.search(r"(?im)^\s*(?:notes?|备注)\s*[:：]", str(record.get("Food Summary", ""))):
                add("High", day, "Diet", "Food Summary 疑似包含全局 notes。", "打开 Diet 记录编辑", "diet", str(record.get("id", "")))

        for record in self.database.get("training_sessions", []):
            day = str(record.get("Date", ""))[:10]
            if re.search(r"new movements?:|automatically registered|新动作提示", str(record.get("Notes", "")), re.I):
                add("Medium", day, "Training", "Training Notes 包含系统生成的新动作提示。", "打开 Training 记录编辑", "training", str(record.get("id", "")))

        for movement in self.database.get("movements", {}).values():
            display_name = self.display_name_for_movement(movement)
            definition = self.movement_definition(movement)
            is_pull_up = movement.get("movement_id") == "BACK_001" or any(
                keyword in normalize_name(
                    " ".join(
                        [
                            display_name,
                            movement.get("name", ""),
                            definition.get("english_name", ""),
                            *(definition.get("aliases") or []),
                        ]
                    )
                )
                for keyword in ("引体向上", "pullup")
            )
            by_date = {}
            for history in movement.get("history", []):
                day = str(history.get("date", ""))[:10]
                by_date[day] = by_date.get(day, 0) + 1
                if not is_pull_up and not history.get("sets") and not history.get("cardio"):
                    add("Medium", day, "Movement", f"“{display_name}”没有 sets。", "打开 Movement 单元格编辑", "movement", movement_id=movement.get("movement_id", ""))
            for day, count in by_date.items():
                if day and count > 1:
                    add("Medium", day, "Movement", f"“{display_name}”同一天出现 {count} 条记录。", "打开 Movement 单元格编辑", "movement", movement_id=movement.get("movement_id", ""))

        for raw_record in self.database.get("raw_entries", []):
            skipped = raw_record.get("skipped_movements") or []
            if skipped:
                add("Low", str(raw_record.get("date", ""))[:10], "Raw Entry", f"有新动作未加入成长表：{'、'.join(skipped)}。", "打开原始输入", "raw", str(raw_record.get("id", "")))

        for area, records in (("Body", self.database.get("daily_records", [])), ("Diet", self.database.get("diet_records", [])), ("Training", self.database.get("training_sessions", []))):
            for day, count in self.date_counts(records).items():
                if count > 1:
                    severity = "Medium" if area == "Training" else "High"
                    action = "确认是一日两练或重复保存" if area == "Training" else f"编辑或覆盖重复 {area} 记录"
                    add(severity, day, area, f"同一天存在 {count} 条记录。", action)

        custom_count = sum(
            1
            for definition in self.movement_dictionary.get("movements", [])
            if str(definition.get("movement_id", "")).startswith("CUSTOM_")
        )
        if custom_count >= 6:
            add("Low", "-", "Movement Dictionary", f"当前有 {custom_count} 个 CUSTOM 动作，建议定期整理。", "打开动作词典管理", "dictionary")
        severity_order = {"High": 0, "Medium": 1, "Low": 2}
        return sorted(issues, key=lambda item: (severity_order[item["severity"]], item["date"], item["area"]))

    def refresh_data_check(self) -> None:
        if not hasattr(self, "data_check_table"):
            return
        self.clear_tree(self.data_check_table)
        self.data_check_issues_by_item = {}
        issues = self.collect_data_issues()
        for index, issue in enumerate(issues):
            item_id = f"issue-{index}"
            can_open = bool(issue.get("target_type"))
            self.data_check_table.insert(
                "",
                "end",
                iid=item_id,
                values=(
                    issue["severity"],
                    issue["date"],
                    issue["area"],
                    issue["issue"],
                    issue["action"],
                    "打开" if can_open else "-",
                ),
            )
            self.data_check_issues_by_item[item_id] = issue
        self.data_check_status.set(f"发现 {len(issues)} 个检查项；此页面不会修改数据。")

    def open_selected_data_issue(self) -> None:
        selection = self.data_check_table.selection()
        if not selection:
            messagebox.showinfo("请选择问题", "请先选择一条可以打开的问题。")
            return
        issue = self.data_check_issues_by_item.get(selection[0], {})
        target_type = issue.get("target_type", "")
        target_id = issue.get("target_id", "")
        if target_type in {"body", "diet", "training"}:
            collections = {
                "body": self.database.get("daily_records", []),
                "diet": self.database.get("diet_records", []),
                "training": self.database.get("training_sessions", []),
            }
            record = next((record for record in collections[target_type] if str(record.get("id", "")) == target_id), None)
            if record:
                self.open_record_from_overview(target_type, record)
                return
        elif target_type == "raw":
            record = next(
                (record for record in self.database.get("raw_entries", []) if str(record.get("id", "")) == target_id),
                None,
            )
            if record:
                self.open_raw_record_detail(record)
                return
        elif target_type == "movement":
            movement_id = issue.get("movement_id", "")
            for cell in self.matrix_cell_records_map.values():
                movement = cell.get("movement", {})
                if movement.get("movement_id") == movement_id and cell.get("date") == issue.get("date"):
                    self.open_movement_history_editor(cell)
                    return
        elif target_type == "dictionary":
            self.open_movement_dictionary_manager()
            return
        messagebox.showinfo("无法定位", "该问题目前无法定位到具体记录，请根据日期和区域手动检查。")

    @staticmethod
    def clear_tree(tree: ttk.Treeview) -> None:
        for item in tree.get_children():
            tree.delete(item)

    def refresh_body(self) -> None:
        self.clear_tree(self.body_table)
        self.body_records_by_item = {}
        records = sorted(self.database["daily_records"], key=lambda row: str(row.get("Date", "")), reverse=True)
        for record in records:
            record_date = record.get("Date", "")
            weight = record.get("Weight (kg)")
            if not record_date and weight in (None, ""):
                continue
            notes = str(record.get("Notes", "") or "")
            context = str(record.get("Context", "") or "")
            if not context:
                context_markers = (
                    "morning",
                    "evening",
                    "fasted",
                    "饭后",
                    "空腹",
                    "早晨",
                    "晚间",
                )
                if any(marker.lower() in notes.lower() for marker in context_markers):
                    context = notes
            cardio = str(record.get("Cardio", "") or "")
            if not cardio and record.get("Cardio Min") not in (None, ""):
                parts = [f"{format_number(record.get('Cardio Min'))} min"]
                if record.get("Incline") not in (None, ""):
                    parts.append(f"incline {format_number(record.get('Incline'))}")
                if record.get("Speed") not in (None, ""):
                    parts.append(f"speed {format_number(record.get('Speed'))}")
                cardio = ", ".join(parts)
            item_id = str(record.get("id") or uuid.uuid4())
            self.body_records_by_item[item_id] = record
            self.body_table.insert(
                "",
                "end",
                iid=item_id,
                values=(
                    str(record_date)[:16],
                    weight if weight is not None else "",
                    make_cell_preview(record.get("Bowel Movement", ""), 24),
                    make_cell_preview(record.get("Training", ""), 38),
                    make_cell_preview(cardio, 34),
                    make_cell_preview(notes, 42),
                ),
            )

    def refresh_diet(self) -> None:
        self.clear_tree(self.diet_table)
        self.diet_records_by_item = {}
        records = sorted(self.database["diet_records"], key=lambda row: str(row.get("Date", "")), reverse=True)
        for record in records:
            item_id = str(record.get("id") or uuid.uuid4())
            self.diet_records_by_item[item_id] = record
            self.diet_table.insert(
                "",
                "end",
                iid=item_id,
                values=(
                    str(record.get("Date", ""))[:10],
                    record.get("Calories (kcal)", ""),
                    record.get("Protein (g)", ""),
                    record.get("Carbs (g)", ""),
                    record.get("Fat (g)", ""),
                    make_cell_preview(record.get("Food Summary", ""), 56),
                    make_cell_preview(record.get("Notes", ""), 38),
                ),
            )

    def display_name_for_movement(self, movement: dict, history: dict | None = None) -> str:
        movement_id = ""
        if history:
            movement_id = str(history.get("movement_id", "") or "")
        movement_id = movement_id or str(movement.get("movement_id", "") or "")
        definition = self.movement_definitions_by_id.get(movement_id)
        if not definition:
            definition = self.movement_definition(movement)
        return definition.get("display_name") or movement.get("name", "")

    def standardized_summary_for_day(self, day_number) -> str:
        try:
            day_number = int(day_number)
        except (TypeError, ValueError):
            return ""
        items = []
        for movement in self.database["movements"].values():
            for history in movement.get("history") or []:
                try:
                    training_day = int(history.get("training_day"))
                except (TypeError, ValueError):
                    continue
                if training_day == day_number:
                    items.append((int(history.get("order") or 0), movement, history))
        if not items:
            return ""
        items.sort(key=lambda item: item[0])
        return "；".join(
            f"第{order}个动作：{self.display_name_for_movement(movement, history)}"
            for order, movement, history in items
        )

    def refresh_training(self) -> None:
        self.clear_tree(self.training_table)
        self.training_records_by_item = {}
        records = sorted(self.database["training_sessions"], key=lambda row: int(row.get("No.", 0) or 0), reverse=True)
        for record in records:
            item_id = str(record.get("id") or uuid.uuid4())
            summary = self.standardized_summary_for_day(record.get("No.")) or record.get("Standardized Summary", "")
            record["Standardized Summary"] = summary
            self.training_records_by_item[item_id] = record
            self.training_table.insert(
                "",
                "end",
                iid=item_id,
                values=(
                    record.get("No.", ""),
                    str(record.get("Date", ""))[:10],
                    make_cell_preview(record.get("Split", ""), 30),
                    make_cell_preview(summary, 52),
                    make_cell_preview(record.get("Notes", ""), 36),
                ),
            )

    def get_movement_matrix_dates(self) -> list[str]:
        return sorted(
            {
                str(record.get("date", ""))[:10]
                for movement in self.database["movements"].values()
                for record in movement.get("history") or []
                if record.get("date")
            }
        )

    def refresh_movements(self) -> None:
        self.clear_tree(self.movement_table)
        self.matrix_cell_detail_map = {}
        self.matrix_cell_records_map = {}
        self.movement_rows_by_item = {}
        dates = self.get_movement_matrix_dates()
        columns = ("movement", *dates)
        self.movement_table.configure(columns=columns)
        self.movement_table.heading("movement", text="动作")
        self.movement_table.column("movement", width=240, minwidth=220, stretch=False, anchor="w")
        for day in dates:
            self.movement_table.heading(day, text=day)
            self.movement_table.column(day, width=160, minwidth=140, stretch=False, anchor="w")

        query = normalize_name(self.movement_search.get()) if hasattr(self, "movement_search") else ""
        movements = sorted(
            self.database["movements"].values(),
            key=lambda item: (
                self.movement_definition(item).get("display_name") or item.get("name", "")
            ).lower(),
        )
        for row_index, movement in enumerate(movements):
            definition = self.movement_definition(movement)
            if definition and not definition.get("active", True):
                continue
            searchable = normalize_name(
                " ".join(
                    [
                        definition.get("display_name", ""),
                        definition.get("english_name", ""),
                        *(definition.get("aliases") or []),
                    ]
                )
            )
            if query and query not in searchable:
                continue
            records_by_date = {}
            for record in movement.get("history") or []:
                record_date = str(record.get("date", ""))[:10]
                if record_date:
                    records_by_date.setdefault(record_date, []).append(record)
            movement_name = definition.get("display_name") or movement.get("name", "")
            item_id = f"movement_{row_index}"
            values = [movement_name]
            details_by_column = {}
            for column_index, day in enumerate(dates, start=2):
                day_records = records_by_date.get(day, [])
                cell_parts = [format_matrix_cell(record) for record in day_records]
                full_cell = " | ".join(part for part in cell_parts if part)
                values.append(make_cell_preview(full_cell, 34))
                if day_records:
                    record_blocks = []
                    for record_number, record in enumerate(day_records, start=1):
                        fields = [
                            f"Record {record_number}",
                            f"Day index: {record.get('training_day') if record.get('training_day') not in (None, '') else '-'}",
                            f"Movement order: {record.get('order') if record.get('order') not in (None, '') else '-'}",
                            f"Sets summary: {format_set_summary(record) or '-'}",
                            f"Raw detail: {record.get('raw') or '-'}",
                            f"Notes: {record.get('notes') or '-'}",
                        ]
                        record_blocks.append("\n".join(fields))
                    details_by_column[f"#{column_index}"] = (
                        f"Movement: {movement_name}\n"
                        f"Date: {day}\n\n"
                        + "\n\n".join(record_blocks)
                    )
            self.movement_table.insert(
                "",
                "end",
                iid=item_id,
                values=values,
            )
            self.movement_rows_by_item[item_id] = movement
            for column_id, content in details_by_column.items():
                self.matrix_cell_detail_map[(item_id, column_id)] = content
            for column_index, day in enumerate(dates, start=2):
                day_records = records_by_date.get(day, [])
                if day_records:
                    self.matrix_cell_records_map[(item_id, f"#{column_index}")] = {
                        "movement": movement,
                        "definition": definition,
                        "date": day,
                        "records": day_records,
                    }

    def open_selected_body_detail(self, _event=None) -> None:
        selection = self.body_table.selection()
        if selection:
            self.open_record_editor("body", selection[0])

    def open_selected_diet_detail(self, _event=None) -> None:
        selection = self.diet_table.selection()
        if selection:
            self.open_record_editor("diet", selection[0])

    def open_selected_training_detail(self, _event=None) -> None:
        selection = self.training_table.selection()
        if selection:
            self.open_record_editor("training", selection[0])

    def open_selected_training_raw_detail(self) -> None:
        selection = self.training_table.selection()
        if not selection:
            messagebox.showinfo("Select a record", "请先选中一条训练记录。")
            return
        record = self.training_records_by_item.get(selection[0], {})
        raw_record = record.get("Raw Record", "")
        title = f"原始训练记录 {str(record.get('Date', ''))[:10]}"
        self.open_detail_window(title, raw_record or "-")

    def open_record_editor(self, record_type: str, item_id: str) -> None:
        config = {
            "body": (
                self.body_records_by_item,
                "Body record",
                ("Date", "Weight (kg)", "Bowel Movement", "Training", "Cardio", "Notes"),
            ),
            "diet": (
                self.diet_records_by_item,
                "Diet record",
                ("Date", "Calories (kcal)", "Protein (g)", "Carbs (g)", "Fat (g)", "Food Summary", "Notes"),
            ),
            "training": (
                self.training_records_by_item,
                "Training record",
                ("Date", "Split", "Raw Record", "Standardized Summary", "Notes"),
            ),
        }
        record_map, title, fields = config[record_type]
        record = record_map.get(item_id)
        if not record:
            messagebox.showerror("Record not found", "找不到选中的记录。")
            return

        window = tk.Toplevel(self)
        window.title(f"Edit {title}")
        window.geometry("780x620")
        window.minsize(620, 460)
        window.configure(bg=COLORS["cream"])
        window.transient(self)
        apply_icon(window)

        body = tk.Frame(window, bg=COLORS["paper"], highlightbackground=COLORS["stone"], highlightthickness=1)
        body.pack(fill="both", expand=True, padx=24, pady=24)
        body.columnconfigure(1, weight=1)
        widgets = {}
        for row, field in enumerate(fields):
            tk.Label(body, text=field, bg=COLORS["paper"], fg=COLORS["muted"], font=("Segoe UI", 9, "bold")).grid(
                row=row, column=0, sticky="nw", padx=18, pady=(12, 4)
            )
            height = 4 if field in {"Food Summary", "Raw Record", "Standardized Summary", "Notes"} else 1
            widget = tk.Text(body, height=height, wrap="word", bg=COLORS["cream"], fg=COLORS["ink"], relief="flat")
            widget.grid(row=row, column=1, sticky="ew", padx=(0, 18), pady=(10, 2))
            widget.insert("1.0", "" if record.get(field) is None else str(record.get(field)))
            widget.configure(state="disabled")
            widgets[field] = widget

        actions = tk.Frame(body, bg=COLORS["paper"])
        actions.grid(row=len(fields), column=0, columnspan=2, sticky="ew", padx=18, pady=16)

        def enable_edit() -> None:
            for widget in widgets.values():
                widget.configure(state="normal")
            save_button.configure(state="normal")

        def save() -> None:
            if self.save_record_edit(record, widgets):
                window.destroy()

        button(actions, "Cancel", window.destroy, "secondary").pack(side="right", padx=(8, 0))
        save_button = button(actions, "Save", save, "primary")
        save_button.pack(side="right", padx=(8, 0))
        save_button.configure(state="disabled")
        button(actions, "Edit", enable_edit, "secondary").pack(side="right")

    def save_record_edit(self, record: dict, widgets: dict) -> bool:
        numeric_fields = {"Weight (kg)", "Calories (kcal)", "Protein (g)", "Carbs (g)", "Fat (g)"}
        values = {}
        for field, widget in widgets.items():
            value = widget.get("1.0", "end").strip()
            if field in numeric_fields:
                try:
                    values[field] = float(value) if value else None
                except ValueError:
                    messagebox.showerror("数值无效", f"{field} 必须是数字或留空。")
                    return False
            else:
                values[field] = value
        tracker_checkpoint, _dictionary_checkpoint = create_undo_checkpoint()
        if tracker_checkpoint is None:
            messagebox.showerror("无法保存", "未能创建保存前检查点，数据未写入。")
            return False
        record.update(values)
        write_json(DATA_FILE, self.database)
        self.refresh_all()
        messagebox.showinfo("Saved", "记录已保存。")
        return True

    def selected_movement_and_definition(self) -> tuple[dict, dict] | tuple[None, None]:
        selection = self.movement_table.selection()
        if not selection:
            messagebox.showinfo("请选择动作", "请先在动作成长表中选中一整行。")
            return None, None
        movement = self.movement_rows_by_item.get(selection[0])
        if not movement:
            messagebox.showerror("找不到动作", "无法定位选中的动作记录。")
            return None, None
        definition = self.movement_definition(movement)
        return movement, definition

    def open_movement_dictionary_manager(self) -> None:
        window = tk.Toplevel(self)
        window.title("动作词典管理")
        window.geometry("1060x720")
        window.minsize(820, 560)
        window.configure(bg=COLORS["cream"])
        window.transient(self)
        apply_icon(window)
        card = tk.Frame(window, bg=COLORS["paper"], highlightbackground=COLORS["stone"], highlightthickness=1)
        card.pack(fill="both", expand=True, padx=24, pady=24)
        card.rowconfigure(3, weight=1)
        card.columnconfigure(0, weight=1)
        tk.Label(card, text="动作词典管理", bg=COLORS["paper"], fg=COLORS["navy"], font=("Georgia", 22, "bold")).grid(row=0, column=0, sticky="w", padx=20, pady=(18, 3))
        tk.Label(card, text="这里只管理动作词条，不显示日期、重量或训练历史。停用不会删除已有记录。", bg=COLORS["paper"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 9)).grid(row=1, column=0, sticky="w", padx=20)
        controls = tk.Frame(card, bg=COLORS["paper"])
        controls.grid(row=2, column=0, sticky="new", padx=20, pady=(12, 6))
        self.dictionary_manager_search = tk.StringVar()
        self.dictionary_manager_status = tk.StringVar(value="全部")
        search = tk.Entry(controls, textvariable=self.dictionary_manager_search, width=28, bg=COLORS["cream"], fg=COLORS["ink"], relief="flat")
        search.pack(side="left", ipady=6)
        status = ttk.Combobox(controls, textvariable=self.dictionary_manager_status, values=("全部", "仅启用", "仅停用"), state="readonly", width=10)
        status.pack(side="left", padx=8)
        button(controls, "编辑信息", self.manager_edit_selected_definition, "secondary").pack(side="right", padx=(7, 0))
        button(controls, "管理别名", self.manager_edit_selected_aliases, "secondary").pack(side="right", padx=(7, 0))
        button(controls, "启用 / 停用", self.manager_toggle_selected_definition, "teal").pack(side="right", padx=(7, 0))
        button(controls, "删除", self.manager_delete_selected_definition, "danger").pack(side="right")
        table_frame = tk.Frame(card, bg=COLORS["paper"])
        table_frame.grid(row=3, column=0, sticky="nsew", padx=2, pady=(0, 2))
        card.rowconfigure(3, weight=1)
        columns = ("status", "display", "english", "muscle", "category", "equipment", "aliases", "id")
        headings = {
            "status": "状态",
            "display": "中文名称",
            "english": "英文名称",
            "muscle": "训练部位",
            "category": "类别",
            "equipment": "器械",
            "aliases": "别名数",
            "id": "movement_id",
        }
        self.dictionary_manager_table = self.build_table_with_scrollbars(table_frame, columns, headings)
        for column, width in (("status", 80), ("display", 170), ("english", 210), ("muscle", 110), ("category", 100), ("equipment", 180), ("aliases", 75), ("id", 110)):
            self.dictionary_manager_table.column(column, width=width, stretch=column in {"display", "english", "equipment"})
        self.dictionary_manager_rows = {}
        self.dictionary_manager_search.trace_add("write", lambda *_: self.refresh_dictionary_manager())
        self.dictionary_manager_status.trace_add("write", lambda *_: self.refresh_dictionary_manager())
        self.dictionary_manager_table.bind("<Double-1>", lambda _event: self.manager_edit_selected_aliases())
        window.bind("<Destroy>", lambda event: self._clear_dictionary_manager(event, window))
        self.refresh_dictionary_manager()

    def _clear_dictionary_manager(self, event, window) -> None:
        if event.widget is window:
            for name in ("dictionary_manager_table", "dictionary_manager_rows", "dictionary_manager_search", "dictionary_manager_status"):
                if hasattr(self, name):
                    delattr(self, name)

    def refresh_dictionary_manager(self) -> None:
        if not hasattr(self, "dictionary_manager_table") or not self.dictionary_manager_table.winfo_exists():
            return
        self.clear_tree(self.dictionary_manager_table)
        self.dictionary_manager_rows = {}
        query = normalize_name(self.dictionary_manager_search.get())
        status_filter = self.dictionary_manager_status.get()
        definitions = sorted(self.movement_dictionary.get("movements", []), key=lambda item: str(item.get("display_name", "")).lower())
        for definition in definitions:
            active = bool(definition.get("active", True))
            if status_filter == "仅启用" and not active:
                continue
            if status_filter == "仅停用" and active:
                continue
            searchable = normalize_name(" ".join([definition.get("display_name", ""), definition.get("english_name", ""), *(definition.get("aliases") or [])]))
            if query and query not in searchable:
                continue
            movement_id = str(definition.get("movement_id", ""))
            self.dictionary_manager_rows[movement_id] = definition
            self.dictionary_manager_table.insert(
                "",
                "end",
                iid=movement_id,
                values=(
                    "启用" if active else "停用",
                    definition.get("display_name", ""),
                    definition.get("english_name", ""),
                    definition.get("muscle_group", ""),
                    definition.get("category", ""),
                    definition.get("equipment", ""),
                    len(definition.get("aliases") or []),
                    movement_id,
                ),
            )

    def manager_selected_definition(self) -> dict | None:
        if not hasattr(self, "dictionary_manager_table"):
            return None
        selection = self.dictionary_manager_table.selection()
        if not selection:
            messagebox.showinfo("请选择动作", "请先在动作词典中选择一个词条。")
            return None
        return self.dictionary_manager_rows.get(selection[0])

    def tracker_movement_by_id(self, movement_id: str) -> dict | None:
        return next(
            (movement for movement in self.database.get("movements", {}).values() if movement.get("movement_id") == movement_id),
            None,
        )

    def manager_edit_selected_definition(self) -> None:
        definition = self.manager_selected_definition()
        if not definition:
            return
        movement = self.tracker_movement_by_id(definition.get("movement_id", ""))
        self.open_movement_definition_editor(movement, definition, self.refresh_dictionary_manager)

    def manager_edit_selected_aliases(self) -> None:
        definition = self.manager_selected_definition()
        if not definition:
            return
        movement = self.tracker_movement_by_id(definition.get("movement_id", ""))
        window = tk.Toplevel(self)
        window.title(f"别名管理 · {definition.get('display_name', '')}")
        window.geometry("620x560")
        window.minsize(520, 440)
        window.configure(bg=COLORS["cream"])
        window.transient(self)
        apply_icon(window)
        card = tk.Frame(window, bg=COLORS["paper"], highlightbackground=COLORS["stone"], highlightthickness=1)
        card.pack(fill="both", expand=True, padx=24, pady=24)
        tk.Label(card, text=definition.get("display_name", ""), bg=COLORS["paper"], fg=COLORS["navy"], font=("Georgia", 20, "bold")).pack(anchor="w", padx=20, pady=(18, 4))
        tk.Label(card, text="别名用于识别不同写法；中文标准名会始终保留。", bg=COLORS["paper"], fg=COLORS["muted"]).pack(anchor="w", padx=20)
        aliases = list(definition.get("aliases") or [])
        listbox = tk.Listbox(card, bg=COLORS["cream"], fg=COLORS["ink"], relief="flat", font=("Microsoft YaHei UI", 10), selectmode="extended")
        listbox.pack(fill="both", expand=True, padx=20, pady=12)

        def redraw() -> None:
            listbox.delete(0, "end")
            for alias in aliases:
                listbox.insert("end", alias)

        entry = tk.Entry(card, bg=COLORS["cream"], fg=COLORS["ink"], relief="flat", font=("Microsoft YaHei UI", 10))
        entry.pack(fill="x", padx=20, ipady=7)

        def add_alias() -> None:
            value = entry.get().strip()
            if value and value not in aliases:
                aliases.append(value)
                entry.delete(0, "end")
                redraw()

        def remove_aliases() -> None:
            protected = definition.get("display_name", "")
            for index in reversed(listbox.curselection()):
                if aliases[index] != protected:
                    aliases.pop(index)
            redraw()

        alias_actions = tk.Frame(card, bg=COLORS["paper"])
        alias_actions.pack(fill="x", padx=20, pady=8)
        button(alias_actions, "添加别名", add_alias, "teal").pack(side="left")
        button(alias_actions, "删除选中别名", remove_aliases, "secondary").pack(side="left", padx=7)

        def save() -> None:
            values = dict(definition)
            values["aliases"] = aliases
            if self.save_movement_definition(movement, definition, values):
                self.refresh_dictionary_manager()
                window.destroy()
                messagebox.showinfo("已保存", "动作别名已更新。")

        footer = tk.Frame(card, bg=COLORS["paper"])
        footer.pack(fill="x", padx=20, pady=(0, 18))
        button(footer, "取消", window.destroy, "secondary").pack(side="right", padx=(8, 0))
        button(footer, "保存别名", save, "primary").pack(side="right")
        redraw()

    def toggle_movement_definition(self, definition: dict) -> bool:
        tracker_checkpoint, _dictionary_checkpoint = create_undo_checkpoint()
        if tracker_checkpoint is None:
            messagebox.showerror("无法保存", "未能创建保存前检查点，状态未修改。")
            return False
        definition["active"] = not bool(definition.get("active", True))
        write_json(MOVEMENT_DICTIONARY_FILE, self.movement_dictionary)
        self.movement_definitions_by_id, self.movement_definitions_by_alias = movement_definition_index(self.movement_dictionary)
        self.refresh_all()
        return True

    def manager_toggle_selected_definition(self) -> None:
        definition = self.manager_selected_definition()
        if definition and self.toggle_movement_definition(definition):
            self.refresh_dictionary_manager()

    def manager_delete_selected_definition(self) -> None:
        definition = self.manager_selected_definition()
        if not definition:
            return
        movement_id = definition.get("movement_id", "")
        movement = self.tracker_movement_by_id(movement_id)
        history_count = len(movement.get("history", [])) if movement else 0
        if not messagebox.askyesno(
            "删除动作词条",
            f"确定删除“{definition.get('display_name', '')}”吗？\n\n"
            f"将同时删除成长表整行和 {history_count} 条结构化历史。原始每日输入仍会保留。",
        ):
            return
        if self.delete_movement_definition(movement_id):
            self.refresh_dictionary_manager()
            messagebox.showinfo("已删除", "动作词条及其结构化历史已删除。")

    def reconcile_unassigned_movements_for_definition(self, definition: dict) -> dict[str, int]:
        """Move CUSTOM/unassigned history and skipped raw movements into one dictionary definition."""
        movement_id = str(definition.get("movement_id", ""))
        alias_keys = {
            normalize_name(str(value))
            for value in [definition.get("display_name", ""), definition.get("english_name", ""), *(definition.get("aliases") or [])]
            if str(value).strip()
        }
        result = {"merged_rows": 0, "merged_history": 0, "restored_skipped": 0}
        if not movement_id or not alias_keys:
            return result

        _target_key, target = self.tracker_movement_for_definition(definition, "")

        def safe_order(value) -> int:
            try:
                return int(value or 0)
            except (TypeError, ValueError):
                return 0

        def history_key(history: dict) -> tuple[str, int, str]:
            return (
                str(history.get("date", ""))[:10],
                safe_order(history.get("order")),
                normalize_name(str(history.get("raw", ""))),
            )

        existing_history = {history_key(history) for history in target.get("history", [])}
        custom_ids_to_remove = set()
        for key, source in list(self.database.get("movements", {}).items()):
            source_id = str(source.get("movement_id", ""))
            if source is target or (source_id and not source_id.startswith("CUSTOM_")):
                continue
            source_names = [source.get("name", ""), *(source.get("aliases") or [])]
            if not any(normalize_name(str(name)) in alias_keys for name in source_names if str(name).strip()):
                continue
            for history in source.get("history", []):
                fingerprint = history_key(history)
                if fingerprint in existing_history:
                    continue
                history["movement_id"] = movement_id
                target.setdefault("history", []).append(history)
                existing_history.add(fingerprint)
                result["merged_history"] += 1
            target["aliases"] = list(
                dict.fromkeys([*target.get("aliases", []), *source_names, *(definition.get("aliases") or [])])
            )
            self.database["movements"].pop(key, None)
            if source_id.startswith("CUSTOM_"):
                custom_ids_to_remove.add(source_id)
            result["merged_rows"] += 1

        if custom_ids_to_remove:
            self.movement_dictionary["movements"] = [
                item
                for item in self.movement_dictionary.get("movements", [])
                if item.get("movement_id") not in custom_ids_to_remove
            ]

        sessions_by_date: dict[str, list[dict]] = {}
        for session in self.database.get("training_sessions", []):
            sessions_by_date.setdefault(str(session.get("Date", ""))[:10], []).append(session)
        for sessions in sessions_by_date.values():
            sessions.sort(key=lambda row: int(row.get("No.") or 0))

        for raw_record in self.database.get("raw_entries", []):
            if raw_record.get("superseded"):
                continue
            skipped = list(raw_record.get("skipped_movements") or [])
            matching_names = {
                normalize_name(str(name))
                for name in skipped
                if normalize_name(str(name)) in alias_keys
            }
            if not matching_names or not str(raw_record.get("text", "")).strip():
                continue
            parsed = self.parse_entry(str(raw_record.get("text", "")))
            entry_date = str(parsed.get("date") or raw_record.get("date", ""))[:10]
            sessions = sessions_by_date.get(entry_date, [])
            if raw_record.get("save_mode") == "append_training":
                session = sessions[-1] if sessions else {}
            else:
                session = sessions[0] if sessions else {}
            training_day = int(session.get("No.") or 0)
            restored_names = set()
            for movement_data in parsed.get("training", {}).get("movements", []):
                candidate_key = normalize_name(str(movement_data.get("name", "")))
                if candidate_key not in matching_names:
                    continue
                history = {
                    "id": str(uuid.uuid4()),
                    "movement_id": movement_id,
                    "date": entry_date,
                    "training_day": training_day,
                    "order": movement_data.get("order"),
                    "sets": movement_data.get("sets") or [],
                    "cardio": movement_data.get("cardio") or {},
                    "raw": movement_data.get("raw", ""),
                    "notes": movement_data.get("notes", ""),
                    "source": "alias reconciliation",
                }
                fingerprint = history_key(history)
                if fingerprint not in existing_history:
                    target.setdefault("history", []).append(history)
                    existing_history.add(fingerprint)
                    result["restored_skipped"] += 1
                restored_names.add(candidate_key)
            remaining = [name for name in skipped if normalize_name(str(name)) not in restored_names]
            if remaining:
                raw_record["skipped_movements"] = remaining
            else:
                raw_record.pop("skipped_movements", None)

        target["name"] = definition.get("display_name") or target.get("name", "")
        target["aliases"] = list(
            dict.fromkeys([*target.get("aliases", []), *(definition.get("aliases") or [])])
        )
        target["history"] = sorted(
            target.get("history", []),
            key=lambda history: (str(history.get("date", "")), safe_order(history.get("order"))),
        )
        return result

    def save_movement_definition(self, movement: dict | None, definition: dict, values: dict) -> bool:
        display_name = str(values.get("display_name", "")).strip()
        if not display_name:
            messagebox.showerror("名称无效", "动作中文名称不能为空。")
            return False
        movement_id = str(definition.get("movement_id", ""))
        conflict = self.movement_definitions_by_alias.get(normalize_name(display_name))
        if conflict and conflict.get("movement_id") != movement_id:
            messagebox.showerror("名称冲突", f"“{display_name}”已经属于动作 {conflict.get('movement_id')}。")
            return False
        aliases = values.get("aliases", [])
        if isinstance(aliases, str):
            aliases = [item.strip() for item in re.split(r"[\n,，;；]+", aliases) if item.strip()]
        old_display = str(definition.get("display_name", "")).strip()
        if old_display and old_display != display_name and old_display not in aliases:
            aliases.append(old_display)
        aliases = list(dict.fromkeys([display_name, *aliases]))
        for alias in aliases:
            conflict = self.movement_definitions_by_alias.get(normalize_name(alias))
            if (
                conflict
                and conflict.get("movement_id") != movement_id
                and not str(conflict.get("movement_id", "")).startswith("CUSTOM_")
            ):
                messagebox.showerror(
                    "别名冲突",
                    f"“{alias}”已经属于正式动作 {conflict.get('movement_id')}，未进行自动归并。",
                )
                return False
        tracker_checkpoint, _dictionary_checkpoint = create_undo_checkpoint()
        if tracker_checkpoint is None:
            messagebox.showerror("无法保存", "未能创建保存前检查点，动作词典未修改。")
            return False
        definition.update(
            {
                "display_name": display_name,
                "english_name": str(values.get("english_name", "")).strip(),
                "aliases": aliases,
                "muscle_group": str(values.get("muscle_group", "")).strip(),
                "category": str(values.get("category", "")).strip(),
                "equipment": str(values.get("equipment", "")).strip(),
                "notes": str(values.get("notes", "")).strip(),
            }
        )
        if movement is not None:
            movement["name"] = display_name
            movement["aliases"] = list(dict.fromkeys([*movement.get("aliases", []), *aliases]))
        reconciliation = self.reconcile_unassigned_movements_for_definition(definition)
        write_json(MOVEMENT_DICTIONARY_FILE, self.movement_dictionary)
        write_json(DATA_FILE, self.database)
        self.movement_definitions_by_id, self.movement_definitions_by_alias = movement_definition_index(
            self.movement_dictionary
        )
        self.refresh_all()
        restored = reconciliation["merged_history"] + reconciliation["restored_skipped"]
        if restored:
            self.quick_status.set(
                f"已归并 {restored} 条历史记录到“{display_name}”。"
            )
        return True

    def edit_selected_movement_definition(self) -> None:
        movement, definition = self.selected_movement_and_definition()
        if not movement:
            return
        if not definition:
            messagebox.showerror("词典条目缺失", "该动作没有可编辑的动作词典条目。")
            return
        self.open_movement_definition_editor(movement, definition)

    def open_movement_definition_editor(self, movement: dict | None, definition: dict, on_saved=None) -> None:
        window = tk.Toplevel(self)
        window.title("编辑动作词典")
        window.geometry("760x680")
        window.minsize(620, 520)
        window.configure(bg=COLORS["cream"])
        window.transient(self)
        apply_icon(window)
        card = tk.Frame(window, bg=COLORS["paper"], highlightbackground=COLORS["stone"], highlightthickness=1)
        card.pack(fill="both", expand=True, padx=24, pady=24)
        card.columnconfigure(1, weight=1)
        fields = (
            ("display_name", "中文名称", 1),
            ("english_name", "英文名称", 1),
            ("aliases", "别名（每行一个）", 5),
            ("muscle_group", "训练部位", 1),
            ("category", "类别", 1),
            ("equipment", "器械", 1),
            ("notes", "备注", 4),
        )
        tk.Label(card, text=f"movement_id: {definition.get('movement_id')}", bg=COLORS["paper"], fg=COLORS["teal"], font=("Segoe UI", 9, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=18, pady=(18, 6))
        widgets = {}
        for row, (field, label, height) in enumerate(fields, start=1):
            tk.Label(card, text=label, bg=COLORS["paper"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 9, "bold")).grid(row=row, column=0, sticky="nw", padx=18, pady=(10, 2))
            widget = tk.Text(card, height=height, wrap="word", bg=COLORS["cream"], fg=COLORS["ink"], relief="flat", padx=8, pady=6)
            widget.grid(row=row, column=1, sticky="ew", padx=(0, 18), pady=(7, 2))
            value = definition.get(field, "")
            if field == "aliases":
                value = "\n".join(value or [])
            widget.insert("1.0", str(value or ""))
            widgets[field] = widget

        def save() -> None:
            values = {field: widget.get("1.0", "end").strip() for field, widget in widgets.items()}
            if self.save_movement_definition(movement, definition, values):
                if on_saved:
                    on_saved()
                window.destroy()
                messagebox.showinfo("已保存", "动作词典和动作成长表名称已更新。")

        actions = tk.Frame(card, bg=COLORS["paper"])
        actions.grid(row=len(fields) + 1, column=0, columnspan=2, sticky="e", padx=18, pady=18)
        button(actions, "取消", window.destroy, "secondary").pack(side="right", padx=(8, 0))
        button(actions, "保存修改", save, "primary").pack(side="right")

    def delete_movement_definition(self, movement_id: str) -> bool:
        tracker_checkpoint, _dictionary_checkpoint = create_undo_checkpoint()
        if tracker_checkpoint is None:
            messagebox.showerror("无法删除", "未能创建删除前检查点，数据未修改。")
            return False
        self.movement_dictionary["movements"] = [
            definition
            for definition in self.movement_dictionary.get("movements", [])
            if definition.get("movement_id") != movement_id
        ]
        self.database["movements"] = {
            key: movement
            for key, movement in self.database.get("movements", {}).items()
            if movement.get("movement_id") != movement_id
        }
        self.movement_definitions_by_id, self.movement_definitions_by_alias = movement_definition_index(
            self.movement_dictionary
        )
        for session in self.database.get("training_sessions", []):
            session["Standardized Summary"] = self.standardized_summary_for_day(session.get("No."))
        write_json(MOVEMENT_DICTIONARY_FILE, self.movement_dictionary)
        write_json(DATA_FILE, self.database)
        self.refresh_all()
        return True

    def delete_selected_movement_definition(self) -> None:
        movement, definition = self.selected_movement_and_definition()
        if not movement:
            return
        movement_id = str(movement.get("movement_id", "") or definition.get("movement_id", ""))
        display_name = definition.get("display_name") or movement.get("name", "")
        history_count = len(movement.get("history", []))
        if not messagebox.askyesno(
            "删除整个动作",
            f"确定删除“{display_name}”吗？\n\n"
            f"将删除动作词典条目、动作成长表整行以及 {history_count} 条动作历史。\n"
            "每日原始输入文本仍会保留，可通过 Undo Last Save 恢复。",
        ):
            return
        if self.delete_movement_definition(movement_id):
            messagebox.showinfo("已删除", f"“{display_name}”及其动作成长记录已删除。")

    def save_movement_history_records(self, updates: list[tuple[dict, dict]]) -> bool:
        validated = []
        for record, values in updates:
            sets_text = str(values.get("sets_text", "")).strip()
            sets = extract_load_blocks(sets_text) if sets_text else []
            if sets_text and not sets:
                messagebox.showerror("组数格式无效", "组数请使用“重量 × 次数 × 组数”，每组一行。")
                return False
            try:
                order_text = str(values.get("order", "")).strip()
                order = int(order_text) if order_text else None
                cardio = {}
                for field in ("duration_minutes", "incline", "speed", "heart_rate"):
                    text = str(values.get(field, "")).strip()
                    cardio[field] = float(text) if text else None
                if not any(value is not None for value in cardio.values()):
                    cardio = {}
            except ValueError:
                messagebox.showerror("数值无效", "动作顺序和有氧参数必须是数字或留空。")
                return False
            validated.append(
                (
                    record,
                    {
                        "order": order,
                        "sets": sets,
                        "cardio": cardio,
                        "raw": str(values.get("raw", "")).strip(),
                        "notes": str(values.get("notes", "")).strip(),
                    },
                )
            )
        tracker_checkpoint, _dictionary_checkpoint = create_undo_checkpoint()
        if tracker_checkpoint is None:
            messagebox.showerror("无法保存", "未能创建保存前检查点，动作记录未修改。")
            return False
        for record, values in validated:
            record.update(values)
        write_json(DATA_FILE, self.database)
        self.refresh_all()
        return True

    def open_movement_history_editor(self, cell: dict) -> None:
        movement = cell["movement"]
        definition = cell.get("definition", {})
        movement_name = definition.get("display_name") or movement.get("name", "")
        window = tk.Toplevel(self)
        window.title(f"编辑动作记录 · {movement_name} · {cell['date']}")
        window.geometry("900x760")
        window.minsize(720, 580)
        window.configure(bg=COLORS["cream"])
        window.transient(self)
        apply_icon(window)
        card = tk.Frame(window, bg=COLORS["paper"], highlightbackground=COLORS["stone"], highlightthickness=1)
        card.pack(fill="both", expand=True, padx=24, pady=24)
        tk.Label(card, text=f"{movement_name} · {cell['date']}", bg=COLORS["paper"], fg=COLORS["navy"], font=("Georgia", 20, "bold")).pack(anchor="w", padx=20, pady=(18, 4))
        tk.Label(card, text="日期和训练日编号保持不变；可以修改动作顺序、组数、备注、原始细节和有氧参数。", bg=COLORS["paper"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=20)
        canvas_frame = tk.Frame(card, bg=COLORS["paper"])
        canvas_frame.pack(fill="both", expand=True, padx=20, pady=12)
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)
        canvas = tk.Canvas(canvas_frame, bg=COLORS["paper"], highlightthickness=0)
        scroll = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        form = tk.Frame(canvas, bg=COLORS["paper"])
        form.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=form, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        edit_rows = []
        for index, record in enumerate(cell["records"], start=1):
            box = tk.Frame(form, bg=COLORS["cream"], highlightbackground=COLORS["stone"], highlightthickness=1)
            box.grid(row=index - 1, column=0, sticky="ew", pady=7)
            form.columnconfigure(0, weight=1)
            box.columnconfigure(1, weight=1)
            tk.Label(box, text=f"记录 {index} · Training Day {record.get('training_day', '-')}", bg=COLORS["cream"], fg=COLORS["teal"], font=("Segoe UI", 9, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 4))
            widgets = {}
            fields = (
                ("order", "动作顺序", record.get("order", ""), 1),
                ("sets_text", "组数", "\n".join(f"{format_number(item.get('weight'))} × {format_number(item.get('reps'))} × {format_number(item.get('sets'))}" for item in record.get("sets", [])), 4),
                ("notes", "动作备注", record.get("notes", ""), 3),
                ("raw", "原始细节", record.get("raw", ""), 4),
                ("duration_minutes", "有氧分钟", (record.get("cardio") or {}).get("duration_minutes", ""), 1),
                ("incline", "坡度", (record.get("cardio") or {}).get("incline", ""), 1),
                ("speed", "速度", (record.get("cardio") or {}).get("speed", ""), 1),
                ("heart_rate", "心率", (record.get("cardio") or {}).get("heart_rate", ""), 1),
            )
            for row, (field, label, value, height) in enumerate(fields, start=1):
                tk.Label(box, text=label, bg=COLORS["cream"], fg=COLORS["muted"]).grid(row=row, column=0, sticky="nw", padx=12, pady=3)
                widget = tk.Text(box, height=height, wrap="word", bg=COLORS["white"], fg=COLORS["ink"], relief="flat")
                widget.grid(row=row, column=1, sticky="ew", padx=(4, 12), pady=3)
                widget.insert("1.0", "" if value is None else str(value))
                widgets[field] = widget
            edit_rows.append((record, widgets))

        def save() -> None:
            updates = [
                (record, {field: widget.get("1.0", "end").strip() for field, widget in widgets.items()})
                for record, widgets in edit_rows
            ]
            if self.save_movement_history_records(updates):
                window.destroy()
                messagebox.showinfo("已保存", "动作成长记录已更新。")

        actions = tk.Frame(card, bg=COLORS["paper"])
        actions.pack(fill="x", padx=20, pady=(0, 18))
        button(actions, "取消", window.destroy, "secondary").pack(side="right", padx=(8, 0))
        button(actions, "保存记录", save, "primary").pack(side="right")

    def open_movement_cell_detail(self, event) -> None:
        item_id = self.movement_table.identify_row(event.y)
        column_id = self.movement_table.identify_column(event.x)
        cell = self.matrix_cell_records_map.get((item_id, column_id))
        if cell:
            self.open_movement_history_editor(cell)

    def open_record_detail_window(self, title: str, record: dict) -> None:
        if not record:
            return
        labels = {
            "Date": "日期",
            "Weight (kg)": "体重 kg",
            "Bowel Movement": "排便记录",
            "Context": "测量背景",
            "Training": "训练",
            "Cardio": "有氧",
            "Notes": "备注",
            "Food Summary": "饮食摘要",
            "Food Summary Original": "饮食摘要原文",
            "Calories (kcal)": "热量",
            "Protein (g)": "蛋白质",
            "Carbs (g)": "碳水",
            "Fat (g)": "脂肪",
            "Notes Original": "备注原文",
            "No.": "编号",
            "Split": "训练部位",
            "Raw Record": "原始记录",
            "Standardized Summary": "标准化摘要",
            "System Notes Original": "系统备注原文",
        }
        lines = [
            f"{labels.get(key, key)}\n{value if value not in (None, '') else '-'}"
            for key, value in record.items()
        ]
        self.open_detail_window(title, "\n\n".join(lines))

    def open_detail_window(self, title: str, content: str) -> None:
        window = tk.Toplevel(self)
        window.title(title)
        window.geometry("720x480")
        window.minsize(560, 380)
        window.configure(bg=COLORS["cream"])
        window.transient(self)
        apply_icon(window)

        card = tk.Frame(window, bg=COLORS["paper"], highlightbackground=COLORS["stone"], highlightthickness=1)
        card.pack(fill="both", expand=True, padx=26, pady=26)
        card.rowconfigure(1, weight=1)
        card.columnconfigure(0, weight=1)
        tk.Label(card, text=title, bg=COLORS["paper"], fg=COLORS["navy"], font=("Georgia", 22, "bold")).grid(
            row=0, column=0, sticky="w", padx=24, pady=(22, 10)
        )

        text_frame = tk.Frame(card, bg=COLORS["paper"])
        text_frame.grid(row=1, column=0, sticky="nsew", padx=24)
        text_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)
        text = tk.Text(
            text_frame,
            wrap="word",
            bg=COLORS["cream"],
            fg=COLORS["ink"],
            relief="flat",
            font=("Microsoft YaHei UI", 11),
            padx=16,
            pady=14,
        )
        text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(text_frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns")
        text.insert("1.0", str(content))
        text.configure(state="disabled")
        button(card, "Close", window.destroy, "primary").grid(row=2, column=0, sticky="e", padx=24, pady=20)

    def close(self) -> None:
        backup_data()
        write_json(DATA_FILE, self.database)
        self.destroy()


def _safe_build_set_item(weight_text: str, reps: str, sets: str) -> dict:
    raw_weight = str(weight_text).strip()
    if re.fullmatch(r"\d+(?:\.\d+)?", raw_weight):
        return {
            "weight": float(raw_weight),
            "reps": int(reps),
            "sets": int(sets),
        }
    return {
        "weight": 0.0,
        "weight_text": raw_weight,
        "reps": int(reps),
        "sets": int(sets),
    }


def extract_load_blocks(text: str) -> list[dict]:
    blocks = []
    normalized = (
        str(text or "")
        .replace("\u00d7", "x")
        .replace("X", "x")
        .replace("*", "x")
        .replace("\uFF0C", ",")
        .replace("\uFF1B", ";")
    )
    progression_pattern = (
        r"\((?P<weights>\d+(?:\.\d+)?(?:\s*[-,;]\s*\d+(?:\.\d+)?)+)\)"
        r"\s*x\s*(?P<reps>\d+)\s*x\s*(?P<sets>\d+)"
    )
    consumed = []
    for match in re.finditer(progression_pattern, normalized, re.I):
        for weight in re.split(r"\s*[-,;]\s*", match.group("weights")):
            item = _safe_build_set_item(weight, match.group("reps"), match.group("sets"))
            if item not in blocks:
                blocks.append(item)
        consumed.append(match.span())

    searchable = normalized
    for start, end in reversed(consumed):
        searchable = searchable[:start] + (" " * (end - start)) + searchable[end:]

    patterns = [
        r"(?P<weight>(?:\u81ea\u91cd)|bodyweight|\d+(?:\.\d+)?)\s*(?:kg|\u516c\u65a4|\u5343\u514b)?\s*x\s*(?P<reps>\d+)\s*(?:reps?)?\s*x\s*(?P<sets>\d+)\s*(?:sets?)?",
        r"(?P<weight>(?:\u81ea\u91cd)|bodyweight|\d+(?:\.\d+)?)\s*(?:kg|\u516c\u65a4|\u5343\u514b)?\s*-\s*(?P<reps>\d+)\s*-\s*(?P<sets>\d+)",
        r"(?P<weight>(?:\u81ea\u91cd)|bodyweight|\d+(?:\.\d+)?)\s*(?:kg|\u516c\u65a4|\u5343\u514b)?\s*(?P<reps>\d+)\s*\u6b21\s*(?P<sets>\d+)\s*\u7ec4?",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, searchable, re.I):
            item = _safe_build_set_item(match.group("weight"), match.group("reps"), match.group("sets"))
            if item not in blocks:
                blocks.append(item)
    return blocks


def extract_training_section(text: str) -> tuple[str, str]:
    lines = str(text or "").splitlines()
    split = ""
    body_lines = []
    in_training = False
    for line in lines:
        if not in_training:
            match = re.match(r"^\s*(?:training|\u8bad\u7ec3)\s*[:\uFF1A]\s*(.*)$", line, re.I)
            if match:
                split = match.group(1).strip()
                in_training = True
            continue
        if re.match(r"^\s*(?:cardio|\u6709\u6c27|diet|\u996e\u98df)\s*[:\uFF1A]", line, re.I):
            break
        body_lines.append(line)
    return split, "\n".join(body_lines).strip()


def extract_global_notes_section(text: str) -> str:
    matches = list(re.finditer(r"(?im)^\s*(?:notes?|\u5907\u6ce8)\s*[:\uFF1A]\s*(.*)$", str(text or "")))
    if not matches:
        return ""
    return matches[-1].group(1).strip()


def format_set_weight(item: dict) -> str:
    weight_text = str(item.get("weight_text", "")).strip()
    if weight_text:
        return weight_text
    return f"{format_number(item.get('weight'))}kg"


def format_set_summary(record: dict) -> str:
    sets = record.get("sets") or []
    if sets:
        return ", ".join(
            f"{format_set_weight(item)}脳{format_number(item.get('reps'))}脳{format_number(item.get('sets'))}"
            for item in sets
        )

    cardio = record.get("cardio") or {}
    cardio_parts = []
    if cardio.get("duration_minutes") is not None:
        cardio_parts.append(f"{format_number(cardio['duration_minutes'])}min")
    if cardio.get("heart_rate") is not None:
        cardio_parts.append(f"HR{format_number(cardio['heart_rate'])}")
    if cardio.get("incline") is not None:
        cardio_parts.append(f"incline {format_number(cardio['incline'])}")
    if cardio.get("speed") is not None:
        cardio_parts.append(f"speed {format_number(cardio['speed'])}")
    return " ".join(cardio_parts) or str(record.get("raw", "")).strip()


def _patched_parse_training_movements(self, training_text: str) -> list[dict]:
    movements = []
    current = None
    pending_order = None
    lines = [line for line in str(training_text or "").splitlines() if line.strip()]

    def finish_current() -> None:
        nonlocal current
        if not current:
            return
        name = strip_movement_metrics(current["name"])
        if name:
            raw_detail = "\n".join(current["raw_lines"])
            definition = self.movement_definitions_by_alias.get(normalize_name(name), {})
            movements.append(
                {
                    "order": current["order"],
                    "name": name,
                    "movement_id": definition.get("movement_id", ""),
                    "display_name": definition.get("display_name", name),
                    "sets": extract_load_blocks(raw_detail),
                    "cardio": {},
                    "raw": raw_detail,
                    "notes": "\n".join(current["notes"]),
                }
            )
        current = None

    for index, raw_line in enumerate(lines):
        stripped = raw_line.strip()
        lower = stripped.lower()
        is_indented = raw_line[:1].isspace()
        next_line = lines[index + 1].strip() if index + 1 < len(lines) else ""

        if re.match(r"^(?:diet|\u996e\u98df|cardio|\u6709\u6c27)\s*[:\uFF1A]", stripped, re.I):
            finish_current()
            break

        number_only_match = re.match(r"^(\d+)\s*(?:[.)])\s*$", stripped)
        if number_only_match:
            finish_current()
            pending_order = int(number_only_match.group(1))
            continue

        order_match = re.match(r"^\s*(\d+)\s*(?:[.)])\s*(?!\d)(.+)$", stripped)
        if order_match:
            finish_current()
            pending_order = None
            current = {
                "order": int(order_match.group(1)),
                "name": order_match.group(2).strip(),
                "raw_lines": [stripped],
                "notes": [],
            }
            continue

        note_match = re.match(r"^(?:notes?|\u5907\u6ce8)\s*[:\uFF1A]\s*(.*)$", stripped, re.I)
        next_definition = self.movement_definitions_by_alias.get(normalize_name(next_line)) if next_line else None
        next_is_movement_boundary = bool(
            re.match(r"^(\d+)\s*(?:[.)])\s*$", next_line)
            or re.match(r"^\s*(\d+)\s*(?:[.)])\s*(?!\d)(.+)$", next_line)
            or next_definition is not None
            or extract_load_blocks(next_line)
        )
        if note_match and current:
            current["raw_lines"].append(stripped)
            current["notes"].append(note_match.group(1).strip())
            if next_is_movement_boundary:
                continue
            if not is_indented and not next_line:
                continue
        if note_match and not is_indented and not next_is_movement_boundary:
            finish_current()
            break

        definition = self.movement_definitions_by_alias.get(normalize_name(stripped))
        starts_unnumbered_movement = (
            not note_match
            and not extract_load_blocks(stripped)
            and not is_cardio_line(stripped)
            and (definition is not None or bool(extract_load_blocks(next_line)))
        )
        if starts_unnumbered_movement:
            finish_current()
            current = {
                "order": pending_order if pending_order is not None else len(movements) + 1,
                "name": stripped,
                "raw_lines": [stripped],
                "notes": [],
            }
            pending_order = None
            continue

        if current:
            current["raw_lines"].append(stripped)
            continue

        if is_cardio_line(stripped):
            movements.append(
                {
                    "order": len(movements) + 1,
                    "name": "Cardio",
                    "movement_id": "",
                    "display_name": "Cardio",
                    "sets": [],
                    "cardio": extract_cardio_metrics(stripped),
                    "raw": stripped,
                    "notes": "",
                }
            )

    finish_current()
    return movements


_ORIGINAL_PARSE_ENTRY = FitnessTrackerApp.parse_entry


def _patched_parse_entry(self, raw: str) -> dict:
    parsed = _ORIGINAL_PARSE_ENTRY(self, raw)
    parsed["body"]["notes"] = extract_global_notes_section(raw)
    return parsed


FitnessTrackerApp.parse_training_movements = _patched_parse_training_movements
FitnessTrackerApp.parse_entry = _patched_parse_entry


def format_set_summary(record: dict) -> str:
    sets = record.get("sets") or []
    if sets:
        return ", ".join(
            f"{format_set_weight(item)}×{format_number(item.get('reps'))}×{format_number(item.get('sets'))}"
            for item in sets
        )

    cardio = record.get("cardio") or {}
    cardio_parts = []
    if cardio.get("duration_minutes") is not None:
        cardio_parts.append(f"{format_number(cardio['duration_minutes'])}min")
    if cardio.get("heart_rate") is not None:
        cardio_parts.append(f"HR{format_number(cardio['heart_rate'])}")
    if cardio.get("incline") is not None:
        cardio_parts.append(f"incline {format_number(cardio['incline'])}")
    if cardio.get("speed") is not None:
        cardio_parts.append(f"speed {format_number(cardio['speed'])}")
    return " ".join(cardio_parts) or str(record.get("raw", "")).strip()


def load_data_check_state() -> dict:
    state = read_json(DATA_CHECK_STATE_FILE, {"acknowledged": {}})
    acknowledged = state.get("acknowledged") if isinstance(state, dict) else {}
    if not isinstance(acknowledged, dict):
        acknowledged = {}
    return {"acknowledged": {str(key): str(value) for key, value in acknowledged.items() if key}}


def data_check_issue_key(issue: dict) -> str:
    payload = {
        "severity": str(issue.get("severity", "")),
        "date": str(issue.get("date", "")),
        "area": str(issue.get("area", "")),
        "issue": str(issue.get("issue", "")),
        "action": str(issue.get("action", "")),
        "target_type": str(issue.get("target_type", "")),
        "target_id": str(issue.get("target_id", "")),
        "movement_id": str(issue.get("movement_id", "")),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def ensure_data_check_state_loaded(self) -> None:
    if not hasattr(self, "data_check_state") or not isinstance(self.data_check_state, dict):
        self.data_check_state = load_data_check_state()


def save_data_check_state(self) -> None:
    ensure_data_check_state_loaded(self)
    write_json(DATA_CHECK_STATE_FILE, self.data_check_state)


def visible_data_issues(self) -> tuple[list[dict], int]:
    ensure_data_check_state_loaded(self)
    all_issues = self.collect_data_issues()
    acknowledged = self.data_check_state.get("acknowledged", {})
    visible = [issue for issue in all_issues if data_check_issue_key(issue) not in acknowledged]
    return visible, len(all_issues) - len(visible)


def _patched_build_data_check_page(self) -> None:
    page = self.page_shell(
        "Data Check",
        "Data check",
        "Rule-based checks for missing, duplicated or suspicious records. This page never changes data.",
    )
    card = tk.Frame(page, bg=COLORS["paper"], highlightbackground=COLORS["stone"], highlightthickness=1)
    card.grid(row=1, column=0, sticky="nsew", padx=32, pady=(0, 25))
    card.rowconfigure(1, weight=1)
    card.columnconfigure(0, weight=1)
    controls = tk.Frame(card, bg=COLORS["paper"])
    controls.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 0))
    self.data_check_status = tk.StringVar(value="尚未检查。")
    tk.Label(
        controls,
        textvariable=self.data_check_status,
        bg=COLORS["paper"],
        fg=COLORS["muted"],
        font=("Microsoft YaHei UI", 9),
    ).pack(side="left")
    button(controls, "重新检查", self.refresh_data_check, "teal").pack(side="right")
    button(controls, "恢复全部已确认", self.reset_acknowledged_data_issues, "secondary").pack(side="right", padx=(0, 8))
    button(controls, "确认并隐藏", self.acknowledge_selected_data_issue, "secondary").pack(side="right", padx=(0, 8))
    button(controls, "打开选中问题", self.open_selected_data_issue, "secondary").pack(side="right", padx=(0, 8))
    table_frame = tk.Frame(card, bg=COLORS["paper"])
    table_frame.grid(row=1, column=0, sticky="nsew")
    columns = ("severity", "date", "area", "issue", "action", "open")
    headings = {
        "severity": "严重程度",
        "date": "日期",
        "area": "区域",
        "issue": "问题",
        "action": "建议操作",
        "open": "Open",
    }
    self.data_check_table = self.build_table_with_scrollbars(table_frame, columns, headings)
    self.data_check_table.column("severity", width=90, stretch=False)
    self.data_check_table.column("date", width=120, stretch=False)
    self.data_check_table.column("area", width=130, stretch=False)
    self.data_check_table.column("issue", width=520)
    self.data_check_table.column("action", width=260)
    self.data_check_table.column("open", width=70, stretch=False, anchor="center")
    self.data_check_issues_by_item = {}
    self.data_check_table.bind("<Double-1>", lambda _event: self.open_selected_data_issue())


def _patched_latest_day_status(self, entry_date: str) -> tuple[str, str]:
    grouped = self.records_on_date(entry_date)
    body = grouped["body"][-1] if grouped["body"] else {}
    diet = grouped["diet"][-1] if grouped["diet"] else {}
    trainings = grouped["training"]
    raw_records = self.raw_records_on_date(entry_date)
    raw_text = "\n".join(str(record.get("text", "")) for record in raw_records)
    weight_status = "✓" if body.get("Weight (kg)") not in (None, "") else "缺失"
    bowel_status = "✓" if str(body.get("Bowel Movement", "")).strip() else "缺失"
    macros_complete = all(
        diet.get(field) not in (None, "")
        for field in ("Calories (kcal)", "Protein (g)", "Carbs (g)", "Fat (g)")
    )
    macro_status = "✓" if macros_complete else "缺失"
    diet_status = "✓" if str(diet.get("Food Summary", "")).strip() else "缺失"
    training_status = f"✓({len(trainings)}次)" if trainings else "缺失"
    cardio = str(body.get("Cardio", "")).strip()
    normalized_cardio = cardio.lower()
    if normalized_cardio in {"none", "无", "否", "没有", "无有氧"}:
        cardio_status = "无有氧"
    elif cardio:
        cardio_status = "✓"
    elif re.search(r"跑步机|爬坡|有氧", raw_text):
        cardio_status = "可能缺失"
    else:
        cardio_status = "缺失"
    new_movement_ids = {
        history.get("movement_id") or movement.get("movement_id")
        for movement in self.database.get("movements", {}).values()
        for history in movement.get("history", [])
        if str(history.get("date", ""))[:10] == entry_date
        and str(history.get("movement_id") or movement.get("movement_id", "")).startswith("CUSTOM_")
    }
    visible_issues, _hidden = visible_data_issues(self)
    high_count = sum(
        1 for issue in visible_issues if issue.get("severity") == "High" and issue.get("date") == entry_date
    )
    status = (
        f"体重 {weight_status}   排便 {bowel_status}\n"
        f"营养 {macro_status}   饮食 {diet_status}\n"
        f"训练 {training_status}   有氧 {cardio_status}\n"
        f"新动作 {len(new_movement_ids)}个   High 问题 {high_count}个"
    )
    return entry_date, status


def _patched_refresh_data_check(self) -> None:
    if not hasattr(self, "data_check_table"):
        return
    self.clear_tree(self.data_check_table)
    self.data_check_issues_by_item = {}
    issues, hidden_count = visible_data_issues(self)
    for index, issue in enumerate(issues):
        item_id = f"issue-{index}"
        can_open = bool(issue.get("target_type"))
        self.data_check_table.insert(
            "",
            "end",
            iid=item_id,
            values=(
                issue["severity"],
                issue["date"],
                issue["area"],
                issue["issue"],
                issue["action"],
                "打开" if can_open else "-",
            ),
        )
        self.data_check_issues_by_item[item_id] = issue
    self.data_check_status.set(f"剩余 {len(issues)} 个检查项，已确认隐藏 {hidden_count} 个。")


def acknowledge_selected_data_issue(self) -> None:
    if not hasattr(self, "data_check_table"):
        return
    selection = self.data_check_table.selection()
    if not selection:
        messagebox.showinfo("请选择问题", "请先选中一条需要确认隐藏的问题。")
        return
    issue = self.data_check_issues_by_item.get(selection[0], {})
    if not issue:
        return
    ensure_data_check_state_loaded(self)
    self.data_check_state.setdefault("acknowledged", {})[data_check_issue_key(issue)] = now_iso()
    save_data_check_state(self)
    self.refresh_data_check()
    if hasattr(self, "today_status_text"):
        self.refresh_quick_overview()


def reset_acknowledged_data_issues(self) -> None:
    ensure_data_check_state_loaded(self)
    acknowledged = self.data_check_state.get("acknowledged", {})
    if not acknowledged:
        messagebox.showinfo("没有已确认项", "当前没有已确认隐藏的问题。")
        return
    if not messagebox.askyesno("恢复已确认项", "要恢复全部已确认隐藏的问题吗？"):
        return
    self.data_check_state["acknowledged"] = {}
    save_data_check_state(self)
    self.refresh_data_check()
    if hasattr(self, "today_status_text"):
        self.refresh_quick_overview()


_ORIGINAL_OPEN_SELECTED_DATA_ISSUE = FitnessTrackerApp.open_selected_data_issue


def _patched_open_selected_data_issue(self) -> None:
    if not hasattr(self, "data_check_table"):
        return
    selection = self.data_check_table.selection()
    if not selection:
        messagebox.showinfo("请选择问题", "请先选中一条可以打开的问题。")
        return
    return _ORIGINAL_OPEN_SELECTED_DATA_ISSUE(self)


FitnessTrackerApp.build_data_check_page = _patched_build_data_check_page
FitnessTrackerApp.latest_day_status = _patched_latest_day_status
FitnessTrackerApp.refresh_data_check = _patched_refresh_data_check
FitnessTrackerApp.acknowledge_selected_data_issue = acknowledge_selected_data_issue
FitnessTrackerApp.reset_acknowledged_data_issues = reset_acknowledged_data_issues
FitnessTrackerApp.open_selected_data_issue = _patched_open_selected_data_issue


HERO_ART_FILE = BASE_DIR / "assets" / "fitness-ledger-hero.png"
BADGE_ART_FILE = BASE_DIR / "assets" / "fitness-ledger-badge.png"

COLORS.update(
    {
        "navy": "#142238",
        "navy_2": "#1B2D46",
        "cream": "#EEE6D8",
        "paper": "#FBF7F0",
        "stone": "#D8CDBE",
        "ink": "#243040",
        "muted": "#6E6A64",
        "teal": "#2E706D",
        "teal_2": "#245957",
        "orange": "#C88943",
        "red": "#A34B43",
        "white": "#FFFDFC",
        "canvas": "#E9DFD2",
        "sidebar": "#0E1B2D",
        "sidebar_panel": "#15263E",
        "line": "#CDBCA6",
        "shadow": "#D4C6B4",
        "hero_text": "#F7F1E6",
        "hero_muted": "#D6C6B0",
        "accent_soft": "#E8D5BE",
        "panel_alt": "#F2EBE1",
    }
)


def button(parent, text: str, command, kind: str = "secondary") -> tk.Button:
    palette = {
        "primary": (COLORS["orange"], COLORS["white"], "#B87934"),
        "secondary": (COLORS["accent_soft"], COLORS["ink"], "#DDC8AB"),
        "nav": (COLORS["sidebar_panel"], "#E8DED0", COLORS["navy_2"]),
        "teal": (COLORS["teal"], COLORS["white"], COLORS["teal_2"]),
        "danger": (COLORS["red"], COLORS["white"], "#8D3C35"),
    }
    background, foreground, active = palette[kind]
    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=background,
        fg=foreground,
        activebackground=active,
        activeforeground=foreground,
        relief="flat",
        bd=0,
        highlightthickness=0,
        padx=18,
        pady=11,
        font=("Microsoft YaHei UI", 10, "bold"),
        cursor="hand2",
    )


def _load_scaled_photo(path: Path, max_width: int, max_height: int) -> tk.PhotoImage | None:
    if not path.exists():
        return None
    image = tk.PhotoImage(file=str(path))
    width = max(1, image.width())
    height = max(1, image.height())
    factor_w = max(1, (width + max_width - 1) // max_width)
    factor_h = max(1, (height + max_height - 1) // max_height)
    factor = max(factor_w, factor_h)
    return image.subsample(factor, factor) if factor > 1 else image


def _ensure_visual_assets(self) -> None:
    if getattr(self, "_visual_assets_ready", False):
        return
    self.hero_art = _load_scaled_photo(HERO_ART_FILE, 1120, 200)
    self.brand_badge = _load_scaled_photo(BADGE_ART_FILE, 112, 112)
    self.brand_badge_small = _load_scaled_photo(BADGE_ART_FILE, 72, 72)
    self._visual_assets_ready = True


def _themed_configure_styles(self) -> None:
    self.style.configure(
        "Treeview",
        background=COLORS["white"],
        fieldbackground=COLORS["white"],
        foreground=COLORS["ink"],
        rowheight=38,
        font=("Microsoft YaHei UI", 9),
        borderwidth=0,
    )
    self.style.configure(
        "Treeview.Heading",
        background=COLORS["panel_alt"],
        foreground=COLORS["muted"],
        font=("Microsoft YaHei UI", 9, "bold"),
        relief="flat",
        padding=(10, 10),
    )
    self.style.map(
        "Treeview",
        background=[("selected", "#E7EEE9")],
        foreground=[("selected", COLORS["navy"])],
    )
    self.style.configure("TNotebook", background=COLORS["paper"], borderwidth=0, tabmargins=(0, 0, 0, 0))
    self.style.configure(
        "TNotebook.Tab",
        background=COLORS["panel_alt"],
        foreground=COLORS["muted"],
        padding=(12, 8),
        font=("Microsoft YaHei UI", 9, "bold"),
    )
    self.style.map(
        "TNotebook.Tab",
        background=[("selected", COLORS["white"])],
        foreground=[("selected", COLORS["navy"])],
    )
    self.style.configure(
        "TCombobox",
        fieldbackground=COLORS["white"],
        background=COLORS["white"],
        foreground=COLORS["ink"],
        bordercolor=COLORS["line"],
        lightcolor=COLORS["line"],
        darkcolor=COLORS["line"],
        arrowsize=14,
        padding=5,
    )


def _build_header_banner(self, parent: tk.Frame, title: str, subtitle: str) -> None:
    banner = tk.Canvas(parent, height=158, bg=COLORS["sidebar"], highlightthickness=0, bd=0)
    banner.pack(fill="x")
    banner.bind(
        "<Configure>",
        lambda event: (
            banner.delete("all"),
            banner.create_image(max(event.width // 2, 1), 79, image=self.hero_art, anchor="center")
            if self.hero_art
            else None,
            banner.create_rectangle(0, 0, event.width, 158, fill=COLORS["sidebar"], stipple="gray25", outline=""),
            banner.create_rectangle(0, 0, min(event.width, 470), 158, fill=COLORS["navy"], outline=""),
            banner.create_line(28, 36, 128, 36, fill=COLORS["orange"], width=2),
            banner.create_text(
                28,
                58,
                text=title,
                anchor="nw",
                fill=COLORS["hero_text"],
                font=("Georgia", 24, "bold"),
            ),
            banner.create_text(
                30,
                104,
                text=subtitle,
                anchor="nw",
                width=max(event.width - 90, 420),
                fill=COLORS["hero_muted"],
                font=("Microsoft YaHei UI", 10),
            ),
        ),
    )


def _themed_page_shell(self, name: str, title: str, subtitle: str) -> tk.Frame:
    page = tk.Frame(self.content, bg=COLORS["canvas"])
    page.grid(row=0, column=0, sticky="nsew")
    page.rowconfigure(1, weight=1)
    page.columnconfigure(0, weight=1)
    header = tk.Frame(page, bg=COLORS["canvas"])
    header.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 16))
    card = tk.Frame(header, bg=COLORS["paper"], highlightbackground=COLORS["line"], highlightthickness=1)
    card.pack(fill="x")
    _build_header_banner(self, card, title, subtitle)
    self.pages[name] = page
    return page


def _themed_build(self) -> None:
    _ensure_visual_assets(self)
    self.configure(bg=COLORS["canvas"])
    self.rowconfigure(0, weight=1)
    self.columnconfigure(1, weight=1)

    sidebar = tk.Frame(self, bg=COLORS["sidebar"], width=252)
    sidebar.grid(row=0, column=0, sticky="ns")
    sidebar.grid_propagate(False)

    brand_panel = tk.Frame(sidebar, bg=COLORS["sidebar_panel"], highlightbackground="#213556", highlightthickness=1)
    brand_panel.pack(fill="x", padx=18, pady=(24, 18))
    if self.brand_badge:
        tk.Label(brand_panel, image=self.brand_badge, bg=COLORS["sidebar_panel"]).pack(anchor="w", padx=18, pady=(18, 10))
    tk.Label(
        brand_panel,
        text="Fitness Ledger",
        bg=COLORS["sidebar_panel"],
        fg=COLORS["white"],
        font=("Georgia", 19, "bold"),
    ).pack(anchor="w", padx=18)
    tk.Label(
        brand_panel,
        text="Body · Diet · Training\nStructured logging with local control",
        bg=COLORS["sidebar_panel"],
        fg="#AAB7C8",
        justify="left",
        font=("Microsoft YaHei UI", 8),
    ).pack(anchor="w", padx=18, pady=(6, 18))

    nav_wrap = tk.Frame(sidebar, bg=COLORS["sidebar"])
    nav_wrap.pack(fill="x", padx=14)
    for name in ("Quick Entry", "Body", "Diet", "Training", "Movement Progress", "Data Check"):
        button(nav_wrap, name, lambda page=name: self.show_page(page), "nav").pack(fill="x", pady=4)

    tk.Frame(sidebar, bg=COLORS["sidebar"]).pack(fill="both", expand=True)
    footer = tk.Frame(sidebar, bg=COLORS["sidebar_panel"], highlightbackground="#213556", highlightthickness=1)
    footer.pack(fill="x", padx=18, pady=(0, 20))
    tk.Label(
        footer,
        text="LOCAL-FIRST",
        bg=COLORS["sidebar_panel"],
        fg=COLORS["orange"],
        font=("Segoe UI", 8, "bold"),
    ).pack(anchor="w", padx=16, pady=(14, 4))
    tk.Label(
        footer,
        text="Automatic backups\nNo cloud dependency",
        bg=COLORS["sidebar_panel"],
        fg="#AAB7C8",
        justify="left",
        font=("Microsoft YaHei UI", 8),
    ).pack(anchor="w", padx=16, pady=(0, 14))

    self.content = tk.Frame(self, bg=COLORS["canvas"])
    self.content.grid(row=0, column=1, sticky="nsew")
    self.content.rowconfigure(0, weight=1)
    self.content.columnconfigure(0, weight=1)

    self.build_quick_entry()
    self.build_body_page()
    self.build_diet_page()
    self.build_training_page()
    self.build_movement_page()
    self.build_data_check_page()


def _themed_quick_entry(self) -> None:
    page = self.page_shell(
        "Quick Entry",
        "Daily Capture",
        "Paste one free-form daily note, then review and save it as structured body, diet, cardio, and training data.",
    )
    body = tk.Frame(page, bg=COLORS["canvas"])
    self.quick_body = body
    body.grid(row=1, column=0, sticky="nsew", padx=28, pady=(0, 24))
    body.rowconfigure(0, weight=1)
    body.columnconfigure(0, weight=1)
    body.columnconfigure(1, weight=0)

    input_card = tk.Frame(body, bg=COLORS["paper"], highlightbackground=COLORS["line"], highlightthickness=1)
    input_card.grid(row=0, column=0, sticky="nsew")
    input_card.rowconfigure(3, weight=1)
    input_card.columnconfigure(0, weight=1)
    tk.Label(
        input_card,
        text="QUICK ENTRY",
        bg=COLORS["paper"],
        fg=COLORS["orange"],
        font=("Segoe UI", 8, "bold"),
    ).grid(row=0, column=0, sticky="w", padx=24, pady=(20, 6))
    tk.Label(
        input_card,
        text="One note in, structured records out.",
        bg=COLORS["paper"],
        fg=COLORS["navy"],
        font=("Georgia", 18, "bold"),
    ).grid(row=1, column=0, sticky="w", padx=24)
    tk.Label(
        input_card,
        text="Mix body data, meals, macros, cardio, and strength work in the same input. The review step stays manual and local.",
        bg=COLORS["paper"],
        fg=COLORS["muted"],
        wraplength=720,
        justify="left",
        font=("Microsoft YaHei UI", 9),
    ).grid(row=2, column=0, sticky="w", padx=24, pady=(8, 10))
    self.raw_text = tk.Text(
        input_card,
        width=1,
        wrap="word",
        font=("Microsoft YaHei UI", 12),
        bg=COLORS["white"],
        fg=COLORS["ink"],
        insertbackground=COLORS["ink"],
        relief="flat",
        highlightbackground=COLORS["line"],
        highlightcolor=COLORS["orange"],
        highlightthickness=1,
        padx=18,
        pady=16,
    )
    self.raw_text.grid(row=3, column=0, sticky="nsew", padx=24, pady=(8, 18))
    actions = tk.Frame(input_card, bg=COLORS["paper"])
    actions.grid(row=4, column=0, sticky="ew", padx=24, pady=(0, 12))
    actions.columnconfigure(0, weight=1)
    button(actions, "Parse & review", self.parse_and_review, "primary").grid(row=0, column=0, sticky="ew")
    button(actions, "Undo Last Save", self.undo_last_save, "danger").grid(row=0, column=1, padx=(10, 0))
    self.quick_status = tk.StringVar(value="Ready for a new daily entry.")
    status_strip = tk.Frame(input_card, bg=COLORS["panel_alt"], highlightbackground=COLORS["line"], highlightthickness=1)
    status_strip.grid(row=5, column=0, sticky="ew", padx=24, pady=(0, 22))
    tk.Label(
        status_strip,
        textvariable=self.quick_status,
        bg=COLORS["panel_alt"],
        fg=COLORS["ink"],
        font=("Microsoft YaHei UI", 9),
        wraplength=760,
        justify="left",
    ).pack(anchor="w", padx=14, pady=10)

    side = tk.Frame(body, bg=COLORS["canvas"], width=448)
    side.grid(row=0, column=1, sticky="nsew", padx=(18, 0))
    side.grid_propagate(False)
    side.rowconfigure(1, weight=1)
    side.columnconfigure(0, weight=1)

    status_card = tk.Frame(side, bg=COLORS["paper"], highlightbackground=COLORS["line"], highlightthickness=1)
    status_card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
    top_bar = tk.Frame(status_card, bg=COLORS["paper"])
    top_bar.pack(fill="x", padx=18, pady=(18, 4))
    if self.brand_badge_small:
        tk.Label(top_bar, image=self.brand_badge_small, bg=COLORS["paper"]).pack(side="left", padx=(0, 10))
    title_wrap = tk.Frame(top_bar, bg=COLORS["paper"])
    title_wrap.pack(side="left", fill="x", expand=True)
    tk.Label(title_wrap, text="Today at a glance", bg=COLORS["paper"], fg=COLORS["navy"], font=("Georgia", 16, "bold")).pack(anchor="w")
    tk.Label(title_wrap, text="Latest record completeness and unresolved checks.", bg=COLORS["paper"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 8)).pack(anchor="w", pady=(3, 0))
    self.today_status_title = tk.StringVar(value="No records yet")
    tk.Label(status_card, textvariable=self.today_status_title, bg=COLORS["paper"], fg=COLORS["orange"], font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=20, pady=(6, 0))
    self.today_status_text = tk.StringVar(value="Save your first entry to show daily status here.")
    tk.Label(
        status_card,
        textvariable=self.today_status_text,
        bg=COLORS["paper"],
        fg=COLORS["ink"],
        font=("Microsoft YaHei UI", 9),
        justify="left",
        wraplength=388,
    ).pack(anchor="w", fill="x", padx=20, pady=(8, 18))

    recent_card = tk.Frame(side, bg=COLORS["paper"], highlightbackground=COLORS["line"], highlightthickness=1)
    recent_card.grid(row=1, column=0, sticky="nsew")
    recent_card.rowconfigure(1, weight=1)
    recent_card.columnconfigure(0, weight=1)
    tk.Label(recent_card, text="Recent saved records", bg=COLORS["paper"], fg=COLORS["navy"], font=("Georgia", 16, "bold")).grid(row=0, column=0, sticky="w", padx=20, pady=(18, 6))
    tk.Label(recent_card, text="Jump straight into editing, raw input, or undo.", bg=COLORS["paper"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 8)).grid(row=0, column=0, sticky="e", padx=20, pady=(20, 6))
    self.recent_records_frame = tk.Frame(recent_card, bg=COLORS["paper"])
    self.recent_records_frame.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
    self.recent_records_frame.columnconfigure(0, weight=1)


FitnessTrackerApp.configure_styles = _themed_configure_styles
FitnessTrackerApp.build = _themed_build
FitnessTrackerApp.page_shell = _themed_page_shell
FitnessTrackerApp.build_quick_entry = _themed_quick_entry


COLORS.update(
    {
        "navy": "#25211C",
        "navy_2": "#322A23",
        "ink": "#28231E",
        "muted": "#7C7267",
        "white": "#FFFDFC",
        "cream": "#F7F1E8",
        "canvas": "#F3ECE3",
        "paper": "#FCF7F1",
        "panel_alt": "#F6EFE6",
        "stone": "#E6DDD1",
        "line": "#E2D8CB",
        "orange": "#B88A4A",
        "red": "#9D6157",
        "teal": "#6D7C73",
        "teal_2": "#5B675F",
        "sidebar": "#161514",
        "sidebar_panel": "#1E1C1A",
        "hero_text": "#2B2621",
        "hero_muted": "#71675C",
        "accent_soft": "#F4ECE2",
        "frost": "#F9F3EC",
    }
)


def button(parent, text: str, command, kind: str = "secondary") -> tk.Button:
    palette = {
        "primary": (COLORS["orange"], COLORS["white"], "#C39556"),
        "secondary": (COLORS["paper"], COLORS["ink"], COLORS["panel_alt"]),
        "nav": (COLORS["sidebar"], "#D9CFBF", "#24211E"),
        "teal": (COLORS["teal"], COLORS["white"], COLORS["teal_2"]),
        "danger": ("#F5E8E4", "#7D4B45", "#EEDAD5"),
    }
    background, foreground, active = palette[kind]
    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=background,
        fg=foreground,
        activebackground=active,
        activeforeground=foreground,
        relief="flat",
        bd=0,
        highlightthickness=0,
        padx=18,
        pady=10,
        font=("Microsoft YaHei UI", 9, "bold"),
        cursor="hand2",
    )


def _surface(parent: tk.Widget, tone: str = "paper", *, border: str | None = None) -> tk.Frame:
    color_map = {
        "paper": COLORS["paper"],
        "panel": COLORS["panel_alt"],
        "canvas": COLORS["canvas"],
        "sidebar": COLORS["sidebar_panel"],
        "frost": COLORS["frost"],
    }
    bg = color_map.get(tone, COLORS["paper"])
    return tk.Frame(parent, bg=bg, highlightbackground=border or COLORS["line"], highlightthickness=1, bd=0)


def _soft_entry(parent: tk.Widget, *, textvariable=None, width: int = 24) -> tk.Entry:
    return tk.Entry(
        parent,
        textvariable=textvariable,
        width=width,
        bg=COLORS["white"],
        fg=COLORS["ink"],
        insertbackground=COLORS["ink"],
        relief="flat",
        highlightbackground=COLORS["line"],
        highlightcolor=COLORS["orange"],
        highlightthickness=1,
        font=("Microsoft YaHei UI", 10),
    )


def _soft_text(parent: tk.Widget, *, height: int = 4, wrap: str = "word") -> tk.Text:
    return tk.Text(
        parent,
        height=height,
        wrap=wrap,
        bg=COLORS["white"],
        fg=COLORS["ink"],
        insertbackground=COLORS["ink"],
        relief="flat",
        highlightbackground=COLORS["line"],
        highlightcolor=COLORS["orange"],
        highlightthickness=1,
        padx=14,
        pady=12,
        font=("Microsoft YaHei UI", 10),
    )


def _pill(parent: tk.Widget, text: str, *, tone: str = "muted") -> tk.Label:
    tones = {
        "muted": (COLORS["panel_alt"], COLORS["muted"]),
        "accent": ("#F2E6D7", COLORS["orange"]),
        "dark": ("#EFE6DA", COLORS["ink"]),
        "success": ("#EAF0EB", COLORS["teal"]),
        "danger": ("#F7E8E4", "#8E514A"),
    }
    bg, fg = tones.get(tone, tones["muted"])
    return tk.Label(
        parent,
        text=text,
        bg=bg,
        fg=fg,
        padx=10,
        pady=4,
        font=("Microsoft YaHei UI", 8, "bold"),
    )


def _tiny_action(parent: tk.Widget, text: str, command, *, tone: str = "secondary") -> tk.Button:
    widget = button(parent, text, command, tone)
    widget.configure(font=("Microsoft YaHei UI", 8, "bold"), padx=10, pady=6)
    return widget


def _clear_children(widget: tk.Widget) -> None:
    for child in widget.winfo_children():
        child.destroy()


def _make_scroll_stack(parent: tk.Widget, *, bg: str) -> tuple[tk.Canvas, ttk.Scrollbar, tk.Frame]:
    parent.rowconfigure(0, weight=1)
    parent.columnconfigure(0, weight=1)
    canvas = tk.Canvas(parent, bg=bg, highlightthickness=0, bd=0)
    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    inner = tk.Frame(canvas, bg=bg)
    window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    def on_configure(_event=None) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))

    def on_canvas(event) -> None:
        canvas.itemconfigure(window_id, width=event.width)

    inner.bind("<Configure>", on_configure)
    canvas.bind("<Configure>", on_canvas)
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")
    return canvas, scrollbar, inner


def _editorial_configure_styles(self) -> None:
    self.style.configure(
        "Treeview",
        background=COLORS["white"],
        fieldbackground=COLORS["white"],
        foreground=COLORS["ink"],
        rowheight=34,
        font=("Microsoft YaHei UI", 9),
        borderwidth=0,
    )
    self.style.configure(
        "Treeview.Heading",
        background=COLORS["paper"],
        foreground=COLORS["muted"],
        font=("Microsoft YaHei UI", 8, "bold"),
        relief="flat",
        padding=(10, 10),
    )
    self.style.map(
        "Treeview",
        background=[("selected", "#EFE6DB")],
        foreground=[("selected", COLORS["ink"])],
    )
    self.style.configure("TNotebook", background=COLORS["canvas"], borderwidth=0, tabmargins=(0, 0, 0, 0))
    self.style.configure(
        "TNotebook.Tab",
        background=COLORS["panel_alt"],
        foreground=COLORS["muted"],
        padding=(14, 8),
        font=("Microsoft YaHei UI", 9, "bold"),
    )
    self.style.map(
        "TNotebook.Tab",
        background=[("selected", COLORS["paper"])],
        foreground=[("selected", COLORS["ink"])],
    )
    self.style.configure(
        "TCombobox",
        fieldbackground=COLORS["white"],
        background=COLORS["white"],
        foreground=COLORS["ink"],
        bordercolor=COLORS["line"],
        lightcolor=COLORS["line"],
        darkcolor=COLORS["line"],
        arrowsize=12,
        padding=5,
    )


def _editorial_page_shell(self, name: str, title: str, subtitle: str) -> tk.Frame:
    page = tk.Frame(self.content, bg=COLORS["canvas"])
    page.grid(row=0, column=0, sticky="nsew")
    page.rowconfigure(1, weight=1)
    page.columnconfigure(0, weight=1)
    header = tk.Frame(page, bg=COLORS["canvas"])
    header.grid(row=0, column=0, sticky="ew", padx=34, pady=(28, 18))
    header.columnconfigure(0, weight=1)
    shell = _surface(header, "paper")
    shell.grid(row=0, column=0, sticky="ew")
    shell.columnconfigure(0, weight=1)
    shell.columnconfigure(1, weight=0)
    lead = tk.Frame(shell, bg=COLORS["paper"])
    lead.grid(row=0, column=0, sticky="nsew", padx=28, pady=24)
    tk.Label(
        lead,
        text=name.upper(),
        bg=COLORS["paper"],
        fg=COLORS["orange"],
        font=("Segoe UI", 8, "bold"),
    ).pack(anchor="w")
    tk.Label(
        lead,
        text=title,
        bg=COLORS["paper"],
        fg=COLORS["hero_text"],
        font=("Georgia", 28),
    ).pack(anchor="w", pady=(4, 8))
    tk.Label(
        lead,
        text=subtitle,
        bg=COLORS["paper"],
        fg=COLORS["hero_muted"],
        wraplength=720,
        justify="left",
        font=("Microsoft YaHei UI", 10),
    ).pack(anchor="w")
    if getattr(self, "hero_art", None):
        art = tk.Label(shell, image=self.hero_art, bg=COLORS["paper"])
        art.grid(row=0, column=1, sticky="e", padx=(0, 12), pady=8)
    self.pages[name] = page
    return page


def _editorial_build(self) -> None:
    _ensure_visual_assets(self)
    self.configure(bg=COLORS["canvas"])
    self.rowconfigure(0, weight=1)
    self.columnconfigure(1, weight=1)

    sidebar = tk.Frame(self, bg=COLORS["sidebar"], width=250)
    sidebar.grid(row=0, column=0, sticky="ns")
    sidebar.grid_propagate(False)

    brand_panel = _surface(sidebar, "sidebar", border="#2A2723")
    brand_panel.pack(fill="x", padx=20, pady=(20, 16))
    if getattr(self, "brand_badge", None):
        tk.Label(brand_panel, image=self.brand_badge, bg=COLORS["sidebar_panel"]).pack(anchor="w", padx=18, pady=(18, 10))
    tk.Label(
        brand_panel,
        text="Fitness Ledger",
        bg=COLORS["sidebar_panel"],
        fg="#F3ECE1",
        font=("Georgia", 20),
    ).pack(anchor="w", padx=18)
    tk.Label(
        brand_panel,
        text="Body · Diet · Training\nPrivate daily logging with local control",
        bg=COLORS["sidebar_panel"],
        fg="#9F968B",
        justify="left",
        font=("Microsoft YaHei UI", 8),
    ).pack(anchor="w", padx=18, pady=(8, 18))

    nav_wrap = tk.Frame(sidebar, bg=COLORS["sidebar"])
    nav_wrap.pack(fill="x", padx=14)
    for name in ("Quick Entry", "Body", "Diet", "Training", "Movement Progress", "Data Check"):
        button(nav_wrap, name, lambda page=name: self.show_page(page), "nav").pack(fill="x", pady=5)

    tk.Frame(sidebar, bg=COLORS["sidebar"]).pack(fill="both", expand=True)
    footer = _surface(sidebar, "sidebar", border="#2A2723")
    footer.pack(fill="x", padx=20, pady=(0, 20))
    tk.Label(
        footer,
        text="LOCAL-FIRST",
        bg=COLORS["sidebar_panel"],
        fg=COLORS["orange"],
        font=("Segoe UI", 8, "bold"),
    ).pack(anchor="w", padx=16, pady=(14, 4))
    tk.Label(
        footer,
        text="Atomic saves\nAutomatic backups\nDesktop + mobile viewer",
        bg=COLORS["sidebar_panel"],
        fg="#9F968B",
        justify="left",
        font=("Microsoft YaHei UI", 8),
    ).pack(anchor="w", padx=16, pady=(0, 14))

    self.content = tk.Frame(self, bg=COLORS["canvas"])
    self.content.grid(row=0, column=1, sticky="nsew")
    self.content.rowconfigure(0, weight=1)
    self.content.columnconfigure(0, weight=1)

    self.build_quick_entry()
    self.build_body_page()
    self.build_diet_page()
    self.build_training_page()
    self.build_movement_page()
    self.build_data_check_page()


def _editorial_build_quick_entry(self) -> None:
    page = self.page_shell(
        "Quick Entry",
        "Daily Capture",
        "Write one free-form daily note, then review it as structured body, nutrition, cardio, and training records before saving.",
    )
    body = tk.Frame(page, bg=COLORS["canvas"])
    body.grid(row=1, column=0, sticky="nsew", padx=34, pady=(0, 26))
    body.rowconfigure(0, weight=1)
    body.columnconfigure(0, weight=1)
    body.columnconfigure(1, weight=0)

    editor = _surface(body, "paper")
    editor.grid(row=0, column=0, sticky="nsew")
    editor.rowconfigure(2, weight=1)
    editor.columnconfigure(0, weight=1)
    tk.Label(editor, text="Capture", bg=COLORS["paper"], fg=COLORS["orange"], font=("Segoe UI", 8, "bold")).grid(
        row=0, column=0, sticky="w", padx=28, pady=(24, 6)
    )
    tk.Label(
        editor,
        text="The input field stays central. Everything else orbits around it.",
        bg=COLORS["paper"],
        fg=COLORS["hero_text"],
        font=("Georgia", 20),
    ).grid(row=1, column=0, sticky="w", padx=28)
    self.raw_text = _soft_text(editor, height=22)
    self.raw_text.grid(row=2, column=0, sticky="nsew", padx=28, pady=(16, 18))
    self.raw_text.configure(font=("Microsoft YaHei UI", 12))
    actions = tk.Frame(editor, bg=COLORS["paper"])
    actions.grid(row=3, column=0, sticky="ew", padx=28, pady=(0, 12))
    actions.columnconfigure(0, weight=1)
    button(actions, "Parse & Review", self.parse_and_review, "primary").grid(row=0, column=0, sticky="ew")
    button(actions, "Undo Last Save", self.undo_last_save, "secondary").grid(row=0, column=1, padx=(12, 0))
    self.quick_status = tk.StringVar(value="Ready for a new daily entry.")
    status_band = _surface(editor, "panel")
    status_band.grid(row=4, column=0, sticky="ew", padx=28, pady=(0, 24))
    tk.Label(
        status_band,
        textvariable=self.quick_status,
        bg=COLORS["panel_alt"],
        fg=COLORS["muted"],
        justify="left",
        wraplength=760,
        font=("Microsoft YaHei UI", 9),
    ).pack(anchor="w", padx=14, pady=10)

    aside = tk.Frame(body, bg=COLORS["canvas"], width=470)
    aside.grid(row=0, column=1, sticky="nsew", padx=(20, 0))
    aside.grid_propagate(False)
    aside.rowconfigure(1, weight=1)
    aside.columnconfigure(0, weight=1)

    overview = _surface(aside, "frost")
    overview.grid(row=0, column=0, sticky="ew", pady=(0, 14))
    top = tk.Frame(overview, bg=COLORS["frost"])
    top.pack(fill="x", padx=18, pady=(18, 6))
    tk.Label(top, text="Today at a glance", bg=COLORS["frost"], fg=COLORS["hero_text"], font=("Georgia", 16)).pack(anchor="w")
    tk.Label(top, text="Latest completeness and unresolved checks.", bg=COLORS["frost"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 8)).pack(anchor="w", pady=(4, 0))
    self.today_status_title = tk.StringVar(value="No records yet")
    tk.Label(overview, textvariable=self.today_status_title, bg=COLORS["frost"], fg=COLORS["orange"], font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=18, pady=(4, 0))
    self.today_status_text = tk.StringVar(value="Save your first entry to surface the daily state here.")
    tk.Label(
        overview,
        textvariable=self.today_status_text,
        bg=COLORS["frost"],
        fg=COLORS["ink"],
        justify="left",
        wraplength=405,
        font=("Microsoft YaHei UI", 9),
    ).pack(anchor="w", fill="x", padx=18, pady=(8, 18))

    recent = _surface(aside, "paper")
    recent.grid(row=1, column=0, sticky="nsew")
    recent.rowconfigure(1, weight=1)
    recent.columnconfigure(0, weight=1)
    head = tk.Frame(recent, bg=COLORS["paper"])
    head.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 8))
    tk.Label(head, text="Recent saved", bg=COLORS["paper"], fg=COLORS["hero_text"], font=("Georgia", 16)).pack(anchor="w")
    tk.Label(head, text="Lightweight jump points for quick correction.", bg=COLORS["paper"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 8)).pack(anchor="w", pady=(4, 0))
    self.recent_records_frame = tk.Frame(recent, bg=COLORS["paper"])
    self.recent_records_frame.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 16))
    self.recent_records_frame.columnconfigure(0, weight=1)


def _build_stream_page(self, name: str, title: str, subtitle: str) -> tuple[tk.Frame, tk.Frame]:
    page = self.page_shell(name, title, subtitle)
    shell = _surface(page, "paper")
    shell.grid(row=1, column=0, sticky="nsew", padx=34, pady=(0, 26))
    shell.rowconfigure(1, weight=1)
    shell.columnconfigure(0, weight=1)
    return page, shell


def _editorial_build_body_page(self) -> None:
    _page, shell = _build_stream_page(
        self,
        "Body",
        "Body Rhythm",
        "Primary signals in a quieter reading flow: weight, bowel movement, training context, cardio, and notes.",
    )
    top = tk.Frame(shell, bg=COLORS["paper"])
    top.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))
    tk.Label(top, text="Flow", bg=COLORS["paper"], fg=COLORS["orange"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
    self.body_status_label = tk.Label(top, text="Latest records first", bg=COLORS["paper"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 9))
    self.body_status_label.pack(anchor="w", pady=(5, 0))
    stack_wrap = tk.Frame(shell, bg=COLORS["paper"])
    stack_wrap.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
    _canvas, _scroll, self.body_stream = _make_scroll_stack(stack_wrap, bg=COLORS["paper"])
    hidden = tk.Frame(shell, bg=COLORS["paper"])
    hidden.grid(row=2, column=0, sticky="nsew")
    hidden.grid_remove()
    columns = ("date", "weight", "bowel", "training", "cardio", "notes")
    headings = {
        "date": "日期",
        "weight": "体重 kg",
        "bowel": "排便记录",
        "training": "训练",
        "cardio": "有氧",
        "notes": "备注",
    }
    self.body_table = self.build_table_with_scrollbars(hidden, columns, headings)
    self.body_table.bind("<Double-1>", self.open_selected_body_detail)
    self.body_records_by_item = {}


def _editorial_build_diet_page(self) -> None:
    _page, shell = _build_stream_page(
        self,
        "Diet",
        "Nutrition Ledger",
        "Meals and macros shift from rigid columns into lighter composition blocks while keeping the same saved data.",
    )
    top = tk.Frame(shell, bg=COLORS["paper"])
    top.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))
    tk.Label(top, text="Nutrition", bg=COLORS["paper"], fg=COLORS["orange"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
    tk.Label(top, text="Each day reads like a structured note instead of a spreadsheet row.", bg=COLORS["paper"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(5, 0))
    stack_wrap = tk.Frame(shell, bg=COLORS["paper"])
    stack_wrap.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
    _canvas, _scroll, self.diet_stream = _make_scroll_stack(stack_wrap, bg=COLORS["paper"])
    hidden = tk.Frame(shell, bg=COLORS["paper"])
    hidden.grid(row=2, column=0, sticky="nsew")
    hidden.grid_remove()
    columns = ("date", "calories", "protein", "carbs", "fat", "food", "notes")
    headings = {
        "date": "日期",
        "calories": "热量",
        "protein": "蛋白质",
        "carbs": "碳水",
        "fat": "脂肪",
        "food": "饮食摘要",
        "notes": "备注",
    }
    self.diet_table = self.build_table_with_scrollbars(hidden, columns, headings)
    self.diet_table.bind("<Double-1>", self.open_selected_diet_detail)
    self.diet_records_by_item = {}


def _editorial_build_training_page(self) -> None:
    _page, shell = _build_stream_page(
        self,
        "Training",
        "Training Reading",
        "Session blocks emphasize reading rhythm first: split, movement summary, notes, and raw text on demand.",
    )
    top = tk.Frame(shell, bg=COLORS["paper"])
    top.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))
    tk.Label(top, text="Sessions", bg=COLORS["paper"], fg=COLORS["orange"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
    tk.Label(top, text="The raw log stays preserved, but no longer dominates the page surface.", bg=COLORS["paper"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(5, 0))
    stack_wrap = tk.Frame(shell, bg=COLORS["paper"])
    stack_wrap.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
    _canvas, _scroll, self.training_stream = _make_scroll_stack(stack_wrap, bg=COLORS["paper"])
    hidden = tk.Frame(shell, bg=COLORS["paper"])
    hidden.grid(row=2, column=0, sticky="nsew")
    hidden.grid_remove()
    columns = ("day", "date", "split", "summary", "notes")
    headings = {
        "day": "编号",
        "date": "日期",
        "split": "训练部位",
        "summary": "标准化摘要",
        "notes": "备注",
    }
    self.training_table = self.build_table_with_scrollbars(hidden, columns, headings)
    self.training_table.bind("<Double-1>", self.open_selected_training_detail)
    self.training_records_by_item = {}


def _editorial_build_movement_page(self) -> None:
    _page, shell = _build_stream_page(
        self,
        "Movement Progress",
        "Movement Timeline",
        "The old matrix becomes a flowing motion archive: movement on the left, dated history blocks on the right.",
    )
    controls = tk.Frame(shell, bg=COLORS["paper"])
    controls.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))
    controls.columnconfigure(1, weight=1)
    tk.Label(controls, text="Search", bg=COLORS["paper"], fg=COLORS["orange"], font=("Segoe UI", 8, "bold")).grid(row=0, column=0, sticky="w")
    self.movement_search = tk.StringVar()
    search = _soft_entry(controls, textvariable=self.movement_search, width=28)
    search.grid(row=0, column=1, sticky="w", padx=(12, 0), ipady=6)
    self.movement_search.trace_add("write", lambda *_: self.refresh_movements())
    action_bar = tk.Frame(controls, bg=COLORS["paper"])
    action_bar.grid(row=0, column=2, sticky="e")
    button(action_bar, "Clear", lambda: self.movement_search.set(""), "secondary").pack(side="left", padx=(0, 8))
    button(action_bar, "Dictionary", self.open_movement_dictionary_manager, "teal").pack(side="left")
    stack_wrap = tk.Frame(shell, bg=COLORS["paper"])
    stack_wrap.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
    _canvas, _scroll, self.movement_stream = _make_scroll_stack(stack_wrap, bg=COLORS["paper"])
    hidden = tk.Frame(shell, bg=COLORS["paper"])
    hidden.grid(row=2, column=0, sticky="nsew")
    hidden.grid_remove()
    columns = ("movement",)
    headings = {"movement": "动作"}
    self.movement_table = self.build_table_with_scrollbars(hidden, columns, headings)
    self.movement_table.bind("<Double-1>", self.open_movement_cell_detail)
    self.matrix_cell_detail_map = {}
    self.matrix_cell_records_map = {}
    self.movement_rows_by_item = {}


def _editorial_build_data_check_page(self) -> None:
    _page, shell = _build_stream_page(
        self,
        "Data Check",
        "Signal Review",
        "Rule-based quality prompts are displayed as reviewable issue threads instead of a rigid grid.",
    )
    controls = tk.Frame(shell, bg=COLORS["paper"])
    controls.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))
    controls.columnconfigure(0, weight=1)
    self.data_check_status = tk.StringVar(value="Not checked yet.")
    tk.Label(controls, textvariable=self.data_check_status, bg=COLORS["paper"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 9)).grid(row=0, column=0, sticky="w")
    tools = tk.Frame(controls, bg=COLORS["paper"])
    tools.grid(row=0, column=1, sticky="e")
    button(tools, "Refresh", self.refresh_data_check, "teal").pack(side="left", padx=(0, 8))
    button(tools, "Restore Hidden", self.reset_acknowledged_data_issues, "secondary").pack(side="left")
    stack_wrap = tk.Frame(shell, bg=COLORS["paper"])
    stack_wrap.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
    _canvas, _scroll, self.data_check_stream = _make_scroll_stack(stack_wrap, bg=COLORS["paper"])
    hidden = tk.Frame(shell, bg=COLORS["paper"])
    hidden.grid(row=2, column=0, sticky="nsew")
    hidden.grid_remove()
    columns = ("severity", "date", "area", "issue", "action", "open")
    headings = {
        "severity": "严重程度",
        "date": "日期",
        "area": "区域",
        "issue": "问题",
        "action": "建议操作",
        "open": "Open",
    }
    self.data_check_table = self.build_table_with_scrollbars(hidden, columns, headings)
    self.data_check_issues_by_item = {}


def _editorial_build_table_with_scrollbars(
    self,
    parent: tk.Widget,
    columns: tuple[str, ...],
    headings: dict[str, str],
    *,
    horizontal: bool = True,
) -> ttk.Treeview:
    parent.rowconfigure(0, weight=1)
    parent.columnconfigure(0, weight=1)
    tree = ttk.Treeview(parent, columns=columns, show="headings")
    for col in columns:
        tree.heading(col, text=headings[col])
        tree.column(col, width=120, anchor="w")
    tree.grid(row=0, column=0, sticky="nsew", padx=(12, 0), pady=(12, 4 if horizontal else 12))
    vertical = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
    vertical.grid(row=0, column=1, sticky="ns", padx=(0, 12), pady=(12, 4 if horizontal else 12))
    tree.configure(yscrollcommand=vertical.set)
    if horizontal:
        horizontal_bar = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
        horizontal_bar.grid(row=1, column=0, sticky="ew", padx=(12, 0), pady=(0, 12))
        tree.configure(xscrollcommand=horizontal_bar.set)
    return tree


def _editorial_render_recent_records(self) -> None:
    dates = self.recent_record_dates(3)
    _clear_children(self.recent_records_frame)
    if not dates:
        tk.Label(self.recent_records_frame, text="No saved records yet.", bg=COLORS["paper"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 9)).grid(row=0, column=0, sticky="w", padx=8, pady=8)
        return
    for row, day in enumerate(dates):
        grouped = self.records_on_date(day)
        body_record = grouped["body"][-1] if grouped["body"] else None
        diet_record = grouped["diet"][-1] if grouped["diet"] else None
        training_record = grouped["training"][-1] if grouped["training"] else None
        raw_records = self.raw_records_on_date(day)
        raw_record = next((record for record in raw_records if not record.get("superseded")), raw_records[0] if raw_records else None)
        weight = body_record.get("Weight (kg)") if body_record else None
        split = training_record.get("Split", "") if training_record else "Rest"
        calories = diet_record.get("Calories (kcal)") if diet_record else None
        row_shell = _surface(self.recent_records_frame, "frost")
        row_shell.grid(row=row, column=0, sticky="ew", padx=4, pady=6)
        row_shell.columnconfigure(0, weight=1)
        head = tk.Frame(row_shell, bg=COLORS["frost"])
        head.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))
        tk.Label(head, text=day, bg=COLORS["frost"], fg=COLORS["hero_text"], font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w")
        tk.Label(
            head,
            text=f"Weight {format_number(weight) or '-'}  ·  {split or '-'}",
            bg=COLORS["frost"],
            fg=COLORS["muted"],
            justify="left",
            wraplength=360,
            font=("Microsoft YaHei UI", 8),
        ).pack(anchor="w", pady=(3, 0))
        tk.Label(
            head,
            text=f"Calories {format_number(calories) or '-'}",
            bg=COLORS["frost"],
            fg=COLORS["muted"],
            justify="left",
            wraplength=360,
            font=("Microsoft YaHei UI", 8),
        ).pack(anchor="w", pady=(2, 0))
        actions = tk.Frame(row_shell, bg=COLORS["frost"])
        actions.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 12))
        _tiny_action(actions, "Body", lambda record=body_record: self.open_record_from_overview("body", record), tone="secondary").pack(side="left", padx=2)
        _tiny_action(actions, "Diet", lambda record=diet_record: self.open_record_from_overview("diet", record), tone="secondary").pack(side="left", padx=2)
        _tiny_action(actions, "Training", lambda record=training_record: self.open_record_from_overview("training", record), tone="secondary").pack(side="left", padx=2)
        _tiny_action(actions, "Raw", lambda record=raw_record: self.open_raw_record_detail(record), tone="secondary").pack(side="left", padx=2)
        _tiny_action(actions, "Undo", self.undo_last_save, tone="secondary").pack(side="left", padx=2)


def _editorial_refresh_quick_overview(self) -> None:
    dates = self.recent_record_dates(3)
    if dates:
        title, status = self.latest_day_status(dates[0])
        self.today_status_title.set(title)
        self.today_status_text.set(status)
    else:
        self.today_status_title.set("No records yet")
        self.today_status_text.set("Save your first entry to surface the daily state here.")
    _editorial_render_recent_records(self)


def _record_section_title(parent: tk.Widget, title: str, meta: str) -> None:
    tk.Label(parent, text=title, bg=parent["bg"], fg=COLORS["hero_text"], font=("Georgia", 18)).pack(anchor="w")
    tk.Label(parent, text=meta, bg=parent["bg"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 8)).pack(anchor="w", pady=(4, 0))


def _editorial_refresh_body(self) -> None:
    if not hasattr(self, "body_stream"):
        return
    _clear_children(self.body_stream)
    self.clear_tree(self.body_table)
    self.body_records_by_item = {}
    records = sorted(self.database["daily_records"], key=lambda row: str(row.get("Date", "")), reverse=True)
    self.body_status_label.configure(text=f"{len(records)} structured body records")
    if not records:
        tk.Label(self.body_stream, text="No body records yet.", bg=COLORS["paper"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=10, pady=12)
        return
    for record in records:
        record_date = record.get("Date", "")
        weight = record.get("Weight (kg)")
        if not record_date and weight in (None, ""):
            continue
        notes = str(record.get("Notes", "") or "")
        cardio = str(record.get("Cardio", "") or "")
        if not cardio and record.get("Cardio Min") not in (None, ""):
            parts = [f"{format_number(record.get('Cardio Min'))} min"]
            if record.get("Incline") not in (None, ""):
                parts.append(f"Incline {format_number(record.get('Incline'))}")
            if record.get("Speed") not in (None, ""):
                parts.append(f"Speed {format_number(record.get('Speed'))}")
            cardio = " · ".join(parts)
        item_id = str(record.get("id") or uuid.uuid4())
        self.body_records_by_item[item_id] = record
        self.body_table.insert(
            "",
            "end",
            iid=item_id,
            values=(
                str(record_date)[:16],
                weight if weight is not None else "",
                make_cell_preview(record.get("Bowel Movement", ""), 24),
                make_cell_preview(record.get("Training", ""), 38),
                make_cell_preview(cardio, 34),
                make_cell_preview(notes, 42),
            ),
        )
        block = _surface(self.body_stream, "frost")
        block.pack(fill="x", padx=8, pady=7)
        header = tk.Frame(block, bg=COLORS["frost"])
        header.pack(fill="x", padx=16, pady=(14, 6))
        _record_section_title(header, str(record_date)[:10], f"Weight {format_number(weight) or '-'} kg")
        chips = tk.Frame(block, bg=COLORS["frost"])
        chips.pack(fill="x", padx=16, pady=(0, 8))
        _pill(chips, f"Bowel · {record.get('Bowel Movement') or '-'}", tone="muted").pack(side="left", padx=(0, 6))
        _pill(chips, f"Training · {make_cell_preview(record.get('Training', ''), 22) or '-'}", tone="dark").pack(side="left", padx=(0, 6))
        _pill(chips, f"Cardio · {make_cell_preview(cardio, 24) or '-'}", tone="success").pack(side="left")
        tk.Label(
            block,
            text=make_cell_preview(notes, 220) or "No notes.",
            bg=COLORS["frost"],
            fg=COLORS["ink"],
            justify="left",
            wraplength=1000,
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w", padx=16, pady=(0, 10))
        actions = tk.Frame(block, bg=COLORS["frost"])
        actions.pack(anchor="w", padx=14, pady=(0, 14))
        _tiny_action(actions, "Open Detail", lambda record=record: self.open_record_detail_window("Body record", record)).pack(side="left", padx=2)
        _tiny_action(actions, "Edit", lambda item_id=item_id: self.open_record_editor("body", item_id), tone="primary").pack(side="left", padx=2)


def _editorial_refresh_diet(self) -> None:
    if not hasattr(self, "diet_stream"):
        return
    _clear_children(self.diet_stream)
    self.clear_tree(self.diet_table)
    self.diet_records_by_item = {}
    records = sorted(self.database["diet_records"], key=lambda row: str(row.get("Date", "")), reverse=True)
    if not records:
        tk.Label(self.diet_stream, text="No nutrition records yet.", bg=COLORS["paper"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=10, pady=12)
        return
    for record in records:
        item_id = str(record.get("id") or uuid.uuid4())
        self.diet_records_by_item[item_id] = record
        self.diet_table.insert(
            "",
            "end",
            iid=item_id,
            values=(
                str(record.get("Date", ""))[:10],
                record.get("Calories (kcal)", ""),
                record.get("Protein (g)", ""),
                record.get("Carbs (g)", ""),
                record.get("Fat (g)", ""),
                make_cell_preview(record.get("Food Summary", ""), 56),
                make_cell_preview(record.get("Notes", ""), 38),
            ),
        )
        block = _surface(self.diet_stream, "frost")
        block.pack(fill="x", padx=8, pady=7)
        head = tk.Frame(block, bg=COLORS["frost"])
        head.pack(fill="x", padx=16, pady=(14, 6))
        _record_section_title(head, str(record.get("Date", ""))[:10], "Nutrition snapshot")
        badges = tk.Frame(block, bg=COLORS["frost"])
        badges.pack(fill="x", padx=16, pady=(0, 8))
        _pill(badges, f"Calories {format_number(record.get('Calories (kcal)')) or '-'}", tone="accent").pack(side="left", padx=(0, 6))
        _pill(badges, f"Protein {format_number(record.get('Protein (g)')) or '-'}g", tone="muted").pack(side="left", padx=(0, 6))
        _pill(badges, f"Carbs {format_number(record.get('Carbs (g)')) or '-'}g", tone="muted").pack(side="left", padx=(0, 6))
        _pill(badges, f"Fat {format_number(record.get('Fat (g)')) or '-'}g", tone="muted").pack(side="left")
        tk.Label(block, text=make_cell_preview(record.get("Food Summary", ""), 320) or "No food summary.", bg=COLORS["frost"], fg=COLORS["ink"], justify="left", wraplength=1000, font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=16, pady=(0, 8))
        notes = str(record.get("Notes", "") or "").strip()
        if notes:
            tk.Label(block, text=make_cell_preview(notes, 220), bg=COLORS["frost"], fg=COLORS["muted"], justify="left", wraplength=1000, font=("Microsoft YaHei UI", 8)).pack(anchor="w", padx=16, pady=(0, 8))
        actions = tk.Frame(block, bg=COLORS["frost"])
        actions.pack(anchor="w", padx=14, pady=(0, 14))
        _tiny_action(actions, "Open Detail", lambda record=record: self.open_record_detail_window("Diet record", record)).pack(side="left", padx=2)
        _tiny_action(actions, "Edit", lambda item_id=item_id: self.open_record_editor("diet", item_id), tone="primary").pack(side="left", padx=2)


def _editorial_refresh_training(self) -> None:
    if not hasattr(self, "training_stream"):
        return
    _clear_children(self.training_stream)
    self.clear_tree(self.training_table)
    self.training_records_by_item = {}
    records = sorted(self.database["training_sessions"], key=lambda row: int(row.get("No.", 0) or 0), reverse=True)
    if not records:
        tk.Label(self.training_stream, text="No training sessions yet.", bg=COLORS["paper"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=10, pady=12)
        return
    for record in records:
        item_id = str(record.get("id") or uuid.uuid4())
        summary = self.standardized_summary_for_day(record.get("No.")) or record.get("Standardized Summary", "")
        record["Standardized Summary"] = summary
        self.training_records_by_item[item_id] = record
        self.training_table.insert(
            "",
            "end",
            iid=item_id,
            values=(
                record.get("No.", ""),
                str(record.get("Date", ""))[:10],
                make_cell_preview(record.get("Split", ""), 30),
                make_cell_preview(summary, 52),
                make_cell_preview(record.get("Notes", ""), 36),
            ),
        )
        block = _surface(self.training_stream, "frost")
        block.pack(fill="x", padx=8, pady=7)
        head = tk.Frame(block, bg=COLORS["frost"])
        head.pack(fill="x", padx=16, pady=(14, 6))
        title = f"{str(record.get('Date', ''))[:10]} · Day {record.get('No.', '-')}"
        split = str(record.get("Split", "") or "No split")
        _record_section_title(head, title, split)
        summary_wrap = tk.Frame(block, bg=COLORS["frost"])
        summary_wrap.pack(fill="x", padx=16, pady=(0, 8))
        _pill(summary_wrap, f"Split · {split}", tone="accent").pack(side="left", padx=(0, 6))
        _pill(summary_wrap, f"Notes {'Yes' if str(record.get('Notes', '')).strip() else 'No'}", tone="muted").pack(side="left")
        tk.Label(block, text=make_cell_preview(summary, 320) or "No structured movement summary.", bg=COLORS["frost"], fg=COLORS["ink"], justify="left", wraplength=1000, font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=16, pady=(0, 8))
        notes = str(record.get("Notes", "") or "").strip()
        if notes:
            tk.Label(block, text=make_cell_preview(notes, 220), bg=COLORS["frost"], fg=COLORS["muted"], justify="left", wraplength=1000, font=("Microsoft YaHei UI", 8)).pack(anchor="w", padx=16, pady=(0, 8))
        actions = tk.Frame(block, bg=COLORS["frost"])
        actions.pack(anchor="w", padx=14, pady=(0, 14))
        _tiny_action(actions, "Open Detail", lambda record=record: self.open_record_detail_window("Training record", record)).pack(side="left", padx=2)
        _tiny_action(actions, "Open Raw", lambda record=record: self.open_detail_window(f"Raw training · {str(record.get('Date', ''))[:10]}", record.get("Raw Record", "") or "-")).pack(side="left", padx=2)
        _tiny_action(actions, "Edit", lambda item_id=item_id: self.open_record_editor("training", item_id), tone="primary").pack(side="left", padx=2)


def _editorial_refresh_movements(self) -> None:
    if not hasattr(self, "movement_stream"):
        return
    _clear_children(self.movement_stream)
    self.clear_tree(self.movement_table)
    self.matrix_cell_detail_map = {}
    self.matrix_cell_records_map = {}
    self.movement_rows_by_item = {}
    dates = self.get_movement_matrix_dates()
    columns = ("movement", *dates)
    self.movement_table.configure(columns=columns)
    self.movement_table.heading("movement", text="动作")
    self.movement_table.column("movement", width=240, minwidth=220, stretch=False, anchor="w")
    for day in dates:
        self.movement_table.heading(day, text=day)
        self.movement_table.column(day, width=160, minwidth=140, stretch=False, anchor="w")
    query = normalize_name(self.movement_search.get()) if hasattr(self, "movement_search") else ""
    movements = sorted(
        self.database["movements"].values(),
        key=lambda item: (self.movement_definition(item).get("display_name") or item.get("name", "")).lower(),
    )
    visible_count = 0
    for row_index, movement in enumerate(movements):
        definition = self.movement_definition(movement)
        if definition and not definition.get("active", True):
            continue
        searchable = normalize_name(" ".join([definition.get("display_name", ""), definition.get("english_name", ""), *(definition.get("aliases") or [])]))
        if query and query not in searchable:
            continue
        visible_count += 1
        item_id = f"movement_{row_index}"
        self.movement_rows_by_item[item_id] = movement
        row = _surface(self.movement_stream, "frost")
        row.pack(fill="x", padx=8, pady=8)
        row.columnconfigure(1, weight=1)
        left = tk.Frame(row, bg=COLORS["frost"], width=250)
        left.grid(row=0, column=0, sticky="nsw", padx=(16, 8), pady=16)
        left.grid_propagate(False)
        name = definition.get("display_name") or movement.get("name", "")
        values = [name]
        english = definition.get("english_name", "")
        tk.Label(left, text=name, bg=COLORS["frost"], fg=COLORS["hero_text"], justify="left", wraplength=220, font=("Georgia", 18)).pack(anchor="w")
        if english and english != name:
            tk.Label(left, text=english, bg=COLORS["frost"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 8)).pack(anchor="w", pady=(4, 0))
        aliases = [alias for alias in (definition.get("aliases") or []) if alias and alias != name][:3]
        if aliases:
            alias_row = tk.Frame(left, bg=COLORS["frost"])
            alias_row.pack(anchor="w", pady=(10, 0))
            for alias in aliases:
                _pill(alias_row, alias, tone="muted").pack(side="left", padx=(0, 6))
        right = tk.Frame(row, bg=COLORS["frost"])
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 16), pady=16)
        records_by_date = {}
        for record in movement.get("history") or []:
            record_date = str(record.get("date", ""))[:10]
            if record_date:
                records_by_date.setdefault(record_date, []).append(record)
        if not records_by_date:
            tk.Label(right, text="No history yet.", bg=COLORS["frost"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 9)).pack(anchor="w")
            continue
        for block_index, day in enumerate(sorted(records_by_date.keys(), reverse=True)):
            day_records = records_by_date[day]
            cell = {
                "movement": movement,
                "definition": definition,
                "date": day,
                "records": day_records,
            }
            column_index = dates.index(day) + 2
            self.matrix_cell_records_map[(item_id, f"#{column_index}")] = cell
            full_cell = " | ".join(part for part in [format_matrix_cell(record) for record in day_records] if part)
            self.matrix_cell_detail_map[(item_id, f"#{column_index}")] = full_cell
            card = _surface(right, "paper")
            card.pack(fill="x", pady=5)
            head = tk.Frame(card, bg=COLORS["paper"])
            head.pack(fill="x", padx=14, pady=(12, 6))
            tk.Label(head, text=day, bg=COLORS["paper"], fg=COLORS["hero_text"], font=("Microsoft YaHei UI", 10, "bold")).pack(side="left")
            ex_text = " / ".join(
                f"Ex {record.get('order') if record.get('order') not in (None, '') else '-'} · Day {record.get('training_day') if record.get('training_day') not in (None, '') else '-'}"
                for record in day_records
            )
            tk.Label(head, text=ex_text, bg=COLORS["paper"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 8)).pack(side="right")
            for record in day_records:
                summary = format_set_summary(record) or str(record.get("raw", "") or "-").strip()
                tk.Label(card, text=f"• {summary}", bg=COLORS["paper"], fg=COLORS["ink"], justify="left", wraplength=820, font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=14, pady=(0, 4))
                notes = str(record.get("notes", "") or "").strip()
                if notes:
                    tk.Label(card, text=notes, bg=COLORS["paper"], fg=COLORS["muted"], justify="left", wraplength=820, font=("Microsoft YaHei UI", 8)).pack(anchor="w", padx=26, pady=(0, 4))
            controls = tk.Frame(card, bg=COLORS["paper"])
            controls.pack(anchor="w", padx=12, pady=(4, 12))
            _tiny_action(controls, "Edit Record", lambda cell=cell: self.open_movement_history_editor(cell), tone="primary").pack(side="left", padx=2)
        values_by_date = {day: "" for day in dates}
        for day in dates:
            day_records = records_by_date.get(day, [])
            full_cell = " | ".join(part for part in [format_matrix_cell(record) for record in day_records] if part)
            values_by_date[day] = make_cell_preview(full_cell, 34)
        self.movement_table.insert("", "end", iid=item_id, values=(values[0], *[values_by_date[day] for day in dates]))
    if not visible_count:
        tk.Label(self.movement_stream, text="No movement matched the current search.", bg=COLORS["paper"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=10, pady=12)


def _open_data_issue_direct(self, issue: dict) -> None:
    target_type = issue.get("target_type", "")
    target_id = issue.get("target_id", "")
    if target_type in {"body", "diet", "training"}:
        collections = {
            "body": self.database.get("daily_records", []),
            "diet": self.database.get("diet_records", []),
            "training": self.database.get("training_sessions", []),
        }
        record = next((record for record in collections[target_type] if str(record.get("id", "")) == target_id), None)
        if record:
            self.open_record_from_overview(target_type, record)
            return
    elif target_type == "raw":
        record = next((record for record in self.database.get("raw_entries", []) if str(record.get("id", "")) == target_id), None)
        if record:
            self.open_raw_record_detail(record)
            return
    elif target_type == "movement":
        movement_id = issue.get("movement_id", "")
        for cell in self.matrix_cell_records_map.values():
            movement = cell.get("movement", {})
            if movement.get("movement_id") == movement_id and cell.get("date") == issue.get("date"):
                self.open_movement_history_editor(cell)
                return
    elif target_type == "dictionary":
        self.open_movement_dictionary_manager()
        return
    messagebox.showinfo("Unable to locate", "This issue cannot be opened directly right now.")


def _acknowledge_data_issue_direct(self, issue: dict) -> None:
    ensure_data_check_state_loaded(self)
    self.data_check_state.setdefault("acknowledged", {})[data_check_issue_key(issue)] = now_iso()
    save_data_check_state(self)
    self.refresh_data_check()
    if hasattr(self, "today_status_text"):
        self.refresh_quick_overview()


def _editorial_refresh_data_check(self) -> None:
    if not hasattr(self, "data_check_stream"):
        return
    _clear_children(self.data_check_stream)
    self.clear_tree(self.data_check_table)
    self.data_check_issues_by_item = {}
    issues, hidden_count = visible_data_issues(self)
    self.data_check_status.set(f"{len(issues)} visible issues · {hidden_count} hidden after acknowledgment")
    if not issues:
        tk.Label(self.data_check_stream, text="No visible issues.", bg=COLORS["paper"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=10, pady=12)
        return
    for index, issue in enumerate(issues):
        item_id = f"issue-{index}"
        self.data_check_issues_by_item[item_id] = issue
        self.data_check_table.insert(
            "",
            "end",
            iid=item_id,
            values=(
                issue["severity"],
                issue["date"],
                issue["area"],
                issue["issue"],
                issue["action"],
                "Open" if issue.get("target_type") else "-",
            ),
        )
        block = _surface(self.data_check_stream, "frost")
        block.pack(fill="x", padx=8, pady=7)
        top = tk.Frame(block, bg=COLORS["frost"])
        top.pack(fill="x", padx=16, pady=(14, 6))
        tone = "danger" if issue.get("severity") == "High" else "accent" if issue.get("severity") == "Medium" else "muted"
        _pill(top, issue.get("severity", "Info"), tone=tone).pack(side="left", padx=(0, 8))
        _pill(top, issue.get("area", "-"), tone="dark").pack(side="left", padx=(0, 8))
        tk.Label(top, text=issue.get("date", ""), bg=COLORS["frost"], fg=COLORS["hero_text"], font=("Microsoft YaHei UI", 10, "bold")).pack(side="right")
        tk.Label(block, text=issue.get("issue", ""), bg=COLORS["frost"], fg=COLORS["ink"], justify="left", wraplength=1020, font=("Microsoft YaHei UI", 10)).pack(anchor="w", padx=16, pady=(0, 6))
        tk.Label(block, text=issue.get("action", ""), bg=COLORS["frost"], fg=COLORS["muted"], justify="left", wraplength=1020, font=("Microsoft YaHei UI", 8)).pack(anchor="w", padx=16, pady=(0, 8))
        actions = tk.Frame(block, bg=COLORS["frost"])
        actions.pack(anchor="w", padx=14, pady=(0, 14))
        if issue.get("target_type"):
            _tiny_action(actions, "Open", lambda issue=issue: _open_data_issue_direct(self, issue), tone="primary").pack(side="left", padx=2)
        _tiny_action(actions, "Acknowledge", lambda issue=issue: _acknowledge_data_issue_direct(self, issue), tone="secondary").pack(side="left", padx=2)


def _build_review_field(parent: tk.Widget, label: str, value, height: int) -> tk.Text:
    wrap = tk.Frame(parent, bg=COLORS["paper"])
    wrap.pack(fill="x", pady=6)
    tk.Label(wrap, text=label, bg=COLORS["paper"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 9, "bold")).pack(anchor="w", pady=(0, 4))
    widget = _soft_text(wrap, height=height)
    widget.pack(fill="x")
    widget.insert("1.0", "" if value is None else str(value))
    return widget


def _editorial_open_review_window(self) -> None:
    parsed = self.pending
    window = tk.Toplevel(self)
    window.title("Review parsed entry")
    window.geometry("1140x860")
    window.minsize(920, 700)
    window.configure(bg=COLORS["canvas"])
    window.transient(self)
    window.grab_set()
    apply_icon(window)

    shell = _surface(window, "paper")
    shell.pack(fill="both", expand=True, padx=24, pady=24)
    shell.rowconfigure(3, weight=1)
    shell.columnconfigure(0, weight=1)
    head = tk.Frame(shell, bg=COLORS["paper"])
    head.grid(row=0, column=0, sticky="ew", padx=26, pady=(22, 8))
    tk.Label(head, text="Review Before Save", bg=COLORS["paper"], fg=COLORS["hero_text"], font=("Georgia", 24)).pack(anchor="w")
    tk.Label(head, text="Correct fields directly below. The original raw entry remains preserved.", bg=COLORS["paper"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(6, 0))

    summary_band = _surface(shell, "frost")
    summary_band.grid(row=1, column=0, sticky="ew", padx=26, pady=(0, 12))
    summary_band.columnconfigure(0, weight=1)
    tk.Label(summary_band, text="Final Summary", bg=COLORS["frost"], fg=COLORS["orange"], font=("Segoe UI", 8, "bold")).grid(row=0, column=0, sticky="w", padx=14, pady=(10, 4))
    self.review_summary_var = tk.StringVar()
    tk.Label(summary_band, textvariable=self.review_summary_var, bg=COLORS["frost"], fg=COLORS["ink"], justify="left", anchor="w", font=("Microsoft YaHei UI", 9)).grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))

    warning_band = _surface(shell, "panel")
    warning_band.grid(row=2, column=0, sticky="ew", padx=26, pady=(0, 10))
    tk.Label(warning_band, text="Warnings", bg=COLORS["panel_alt"], fg="#8F564D", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=14, pady=(10, 4))
    self.review_warning_text = tk.Text(warning_band, height=4, wrap="word", bg=COLORS["panel_alt"], fg=COLORS["ink"], relief="flat", font=("Microsoft YaHei UI", 9), padx=8, pady=4)
    self.review_warning_text.pack(fill="x", padx=10, pady=(0, 10))

    canvas_wrap = tk.Frame(shell, bg=COLORS["paper"])
    canvas_wrap.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 12))
    canvas_wrap.rowconfigure(0, weight=1)
    canvas_wrap.columnconfigure(0, weight=1)
    canvas = tk.Canvas(canvas_wrap, bg=COLORS["paper"], highlightthickness=0)
    scroll = ttk.Scrollbar(canvas_wrap, orient="vertical", command=canvas.yview)
    form = tk.Frame(canvas, bg=COLORS["paper"])
    form.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
    window_id = canvas.create_window((0, 0), window=form, anchor="nw")
    canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))
    canvas.configure(yscrollcommand=scroll.set)
    canvas.grid(row=0, column=0, sticky="nsew")
    scroll.grid(row=0, column=1, sticky="ns")

    self.review_widgets = {"body": {}, "diet": {}, "training": {}}
    self.review_movement_widgets = []

    def section(title: str, subtitle: str) -> tk.Frame:
        box = _surface(form, "frost")
        box.pack(fill="x", padx=6, pady=8)
        heading = tk.Frame(box, bg=COLORS["frost"])
        heading.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(heading, text=title, bg=COLORS["frost"], fg=COLORS["hero_text"], font=("Georgia", 18)).pack(anchor="w")
        tk.Label(heading, text=subtitle, bg=COLORS["frost"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 8)).pack(anchor="w", pady=(4, 0))
        content = tk.Frame(box, bg=COLORS["frost"])
        content.pack(fill="x", padx=16, pady=(0, 16))
        return content

    parsed_body = parsed["body"]
    parsed_diet = parsed["diet"]
    parsed_training = parsed["training"]

    body_box = section("Body", "Primary daily signals")
    self.review_widgets["date"] = _build_review_field(body_box, "Date", parsed["date"], 1)
    self.review_widgets["body"]["weight"] = _build_review_field(body_box, "Weight", parsed_body.get("weight"), 1)
    self.review_widgets["body"]["bowel_movement"] = _build_review_field(body_box, "Bowel Movement", parsed_body.get("bowel_movement"), 1)
    self.review_widgets["body"]["training_summary"] = _build_review_field(body_box, "Training Split", parsed_body.get("training_summary"), 1)
    self.review_widgets["body"]["cardio_summary"] = _build_review_field(body_box, "Cardio", parsed_body.get("cardio_summary"), 2)
    self.review_widgets["body"]["notes"] = _build_review_field(body_box, "Notes", parsed_body.get("notes"), 4)

    diet_box = section("Diet", "Macros and food summary")
    self.review_widgets["diet"]["calories"] = _build_review_field(diet_box, "Calories", parsed_diet.get("calories"), 1)
    self.review_widgets["diet"]["protein"] = _build_review_field(diet_box, "Protein", parsed_diet.get("protein"), 1)
    self.review_widgets["diet"]["carbs"] = _build_review_field(diet_box, "Carbs", parsed_diet.get("carbs"), 1)
    self.review_widgets["diet"]["fat"] = _build_review_field(diet_box, "Fat", parsed_diet.get("fat"), 1)
    self.review_widgets["diet"]["food_summary"] = _build_review_field(diet_box, "Food Summary", parsed_diet.get("food_summary"), 7)
    self.review_widgets["diet"]["notes"] = _build_review_field(diet_box, "Notes", parsed_diet.get("notes"), 3)

    training_box = section("Training", "Structured output before save")
    self.review_widgets["training"]["split"] = _build_review_field(training_box, "Split", parsed_training.get("split"), 1)
    self.review_widgets["training"]["standardized_summary"] = _build_review_field(training_box, "Structured Summary", parsed_training.get("standardized_summary"), 4)
    self.review_widgets["training"]["notes"] = _build_review_field(training_box, "Training Notes", parsed_training.get("notes"), 4)

    movement_box = section("Movements", "Review mapping, naming, and notes")
    mapping_values = [
        f"{definition['movement_id']} | {definition.get('display_name', '')}"
        for definition in self.movement_dictionary.get("movements", [])
        if definition.get("movement_id") and definition.get("active", True)
    ]
    for movement in parsed_training["movements"]:
        card = _surface(movement_box, "paper")
        card.pack(fill="x", pady=6)
        title = tk.Frame(card, bg=COLORS["paper"])
        title.pack(fill="x", padx=14, pady=(12, 6))
        tk.Label(title, text=f"{movement.get('order')}. {movement.get('name', '')}", bg=COLORS["paper"], fg=COLORS["hero_text"], font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w")
        sets_text = ", ".join(f"{item.get('weight_text') or format_number(item.get('weight'))} × {item['reps']} × {item['sets']}" for item in movement.get("sets", [])) or "No structured sets yet"
        tk.Label(title, text=sets_text, bg=COLORS["paper"], fg=COLORS["muted"], justify="left", wraplength=900, font=("Microsoft YaHei UI", 8)).pack(anchor="w", pady=(4, 0))
        content = tk.Frame(card, bg=COLORS["paper"])
        content.pack(fill="x", padx=14, pady=(0, 12))
        standard_name = _soft_entry(content, width=42)
        standard_name.pack(fill="x", pady=(0, 8))
        standard_name.insert(0, movement.get("display_name") or movement.get("name", ""))
        tk.Label(content, text="Movement Note", bg=COLORS["paper"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 8, "bold")).pack(anchor="w", pady=(0, 4))
        notes_widget = _soft_text(content, height=2)
        notes_widget.pack(fill="x", pady=(0, 8))
        notes_widget.insert("1.0", movement.get("notes", ""))
        combo_row = tk.Frame(content, bg=COLORS["paper"])
        combo_row.pack(fill="x")
        action_values = (
            ["Use current match", "Map to existing movement", "Keep raw training only", "Cancel whole save"]
            if movement.get("movement_id")
            else ["Add to dictionary", "Map to existing movement", "Keep raw training only", "Cancel whole save"]
        )
        action = ttk.Combobox(combo_row, values=action_values, state="readonly", width=24)
        action.set(action_values[0])
        action.pack(side="left")
        group = ttk.Combobox(
            combo_row,
            values=["Shoulder", "Chest", "Back", "Legs", "Arms", "Core", "Cardio", "Other"],
            state="readonly",
            width=14,
        )
        group.pack(side="left", padx=(10, 0))
        mapping = ttk.Combobox(combo_row, values=mapping_values, state="readonly", width=42)
        movement_id = movement.get("movement_id", "")
        if movement_id:
            current = next((value for value in mapping_values if value.startswith(f"{movement_id} | ")), "")
            mapping.set(current)
        mapping.pack(side="left", padx=(10, 0), fill="x", expand=True)
        self.review_movement_widgets.append({"standard_name": standard_name, "notes": notes_widget, "action": action, "group": group, "mapping": mapping})

    actions = tk.Frame(shell, bg=COLORS["paper"])
    actions.grid(row=4, column=0, sticky="ew", padx=26, pady=(0, 22))
    button(actions, "Refresh Warnings", self.refresh_review_warnings, "secondary").pack(side="left")
    button(actions, "Cancel", window.destroy, "secondary").pack(side="right", padx=(8, 0))
    button(actions, "Confirm & Save", lambda: self.confirm_review(window), "primary").pack(side="right")

    for section_widgets in self.review_widgets.values():
        if isinstance(section_widgets, dict):
            for widget in section_widgets.values():
                widget.bind("<KeyRelease>", lambda _event: self.after_idle(self.refresh_review_summary))
    self.review_widgets["date"].bind("<KeyRelease>", lambda _event: self.after_idle(self.refresh_review_summary))
    for controls in self.review_movement_widgets:
        controls["standard_name"].bind("<KeyRelease>", lambda _event: self.after_idle(self.refresh_review_summary))
        controls["notes"].bind("<KeyRelease>", lambda _event: self.after_idle(self.refresh_review_summary))
        controls["action"].bind("<<ComboboxSelected>>", lambda _event: self.after_idle(self.refresh_review_summary))
        controls["mapping"].bind("<<ComboboxSelected>>", lambda _event: self.after_idle(self.refresh_review_summary))
    self.refresh_review_warnings()


def _editorial_open_record_editor(self, record_type: str, item_id: str) -> None:
    config = {
        "body": (self.body_records_by_item, "Body Record", ("Date", "Weight (kg)", "Bowel Movement", "Training", "Cardio", "Notes")),
        "diet": (self.diet_records_by_item, "Diet Record", ("Date", "Calories (kcal)", "Protein (g)", "Carbs (g)", "Fat (g)", "Food Summary", "Notes")),
        "training": (self.training_records_by_item, "Training Record", ("Date", "Split", "Raw Record", "Standardized Summary", "Notes")),
    }
    record_map, title, fields = config[record_type]
    record = record_map.get(item_id)
    if not record:
        messagebox.showerror("Record not found", "Unable to find the selected record.")
        return
    window = tk.Toplevel(self)
    window.title(f"Edit {title}")
    window.geometry("820x700")
    window.minsize(680, 520)
    window.configure(bg=COLORS["canvas"])
    window.transient(self)
    apply_icon(window)
    shell = _surface(window, "paper")
    shell.pack(fill="both", expand=True, padx=24, pady=24)
    shell.rowconfigure(1, weight=1)
    shell.columnconfigure(0, weight=1)
    head = tk.Frame(shell, bg=COLORS["paper"])
    head.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 10))
    tk.Label(head, text=title, bg=COLORS["paper"], fg=COLORS["hero_text"], font=("Georgia", 22)).pack(anchor="w")
    tk.Label(head, text="Editable structured record. Save uses the existing backup and atomic write flow.", bg=COLORS["paper"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(5, 0))
    form_wrap = tk.Frame(shell, bg=COLORS["paper"])
    form_wrap.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 12))
    _canvas, _scroll, inner = _make_scroll_stack(form_wrap, bg=COLORS["paper"])
    widgets = {}
    for field in fields:
        section = _surface(inner, "frost")
        section.pack(fill="x", padx=6, pady=7)
        content = tk.Frame(section, bg=COLORS["frost"])
        content.pack(fill="x", padx=14, pady=(12, 12))
        tk.Label(content, text=field, bg=COLORS["frost"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 9, "bold")).pack(anchor="w", pady=(0, 4))
        height = 5 if field in {"Food Summary", "Raw Record", "Standardized Summary", "Notes"} else 1
        widget = _soft_text(content, height=height)
        widget.pack(fill="x")
        widget.insert("1.0", "" if record.get(field) is None else str(record.get(field)))
        widget.configure(state="disabled")
        widgets[field] = widget
    actions = tk.Frame(shell, bg=COLORS["paper"])
    actions.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 20))

    def enable_edit() -> None:
        for widget in widgets.values():
            widget.configure(state="normal")
        save_button.configure(state="normal")

    def save() -> None:
        if self.save_record_edit(record, widgets):
            window.destroy()

    button(actions, "Cancel", window.destroy, "secondary").pack(side="right", padx=(8, 0))
    save_button = button(actions, "Save", save, "primary")
    save_button.pack(side="right", padx=(8, 0))
    save_button.configure(state="disabled")
    button(actions, "Edit", enable_edit, "secondary").pack(side="right")


def _editorial_open_detail_window(self, title: str, content: str) -> None:
    window = tk.Toplevel(self)
    window.title(title)
    window.geometry("760x520")
    window.minsize(600, 420)
    window.configure(bg=COLORS["canvas"])
    window.transient(self)
    apply_icon(window)
    shell = _surface(window, "paper")
    shell.pack(fill="both", expand=True, padx=24, pady=24)
    shell.rowconfigure(1, weight=1)
    shell.columnconfigure(0, weight=1)
    head = tk.Frame(shell, bg=COLORS["paper"])
    head.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 10))
    tk.Label(head, text=title, bg=COLORS["paper"], fg=COLORS["hero_text"], font=("Georgia", 22)).pack(anchor="w")
    tk.Label(head, text="Read-only detail view.", bg=COLORS["paper"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(5, 0))
    text_shell = _surface(shell, "frost")
    text_shell.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 14))
    text_shell.rowconfigure(0, weight=1)
    text_shell.columnconfigure(0, weight=1)
    text = tk.Text(text_shell, wrap="word", bg=COLORS["frost"], fg=COLORS["ink"], relief="flat", font=("Microsoft YaHei UI", 11), padx=16, pady=14)
    text.grid(row=0, column=0, sticky="nsew")
    scroll = ttk.Scrollbar(text_shell, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=scroll.set)
    scroll.grid(row=0, column=1, sticky="ns")
    text.insert("1.0", str(content))
    text.configure(state="disabled")
    actions = tk.Frame(shell, bg=COLORS["paper"])
    actions.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 20))
    button(actions, "Close", window.destroy, "primary").pack(side="right")


FitnessTrackerApp.configure_styles = _editorial_configure_styles
FitnessTrackerApp.page_shell = _editorial_page_shell
FitnessTrackerApp.build = _editorial_build
FitnessTrackerApp.build_quick_entry = _editorial_build_quick_entry
FitnessTrackerApp.build_body_page = _editorial_build_body_page
FitnessTrackerApp.build_diet_page = _editorial_build_diet_page
FitnessTrackerApp.build_training_page = _editorial_build_training_page
FitnessTrackerApp.build_movement_page = _editorial_build_movement_page
FitnessTrackerApp.build_data_check_page = _editorial_build_data_check_page
FitnessTrackerApp.build_table_with_scrollbars = _editorial_build_table_with_scrollbars
FitnessTrackerApp.refresh_quick_overview = _editorial_refresh_quick_overview
FitnessTrackerApp.refresh_body = _editorial_refresh_body
FitnessTrackerApp.refresh_diet = _editorial_refresh_diet
FitnessTrackerApp.refresh_training = _editorial_refresh_training
FitnessTrackerApp.refresh_movements = _editorial_refresh_movements
FitnessTrackerApp.refresh_data_check = _editorial_refresh_data_check
FitnessTrackerApp.open_review_window = _editorial_open_review_window
FitnessTrackerApp.open_record_editor = _editorial_open_record_editor
FitnessTrackerApp.open_detail_window = _editorial_open_detail_window


# Nike-inspired product UI layer. This intentionally changes presentation only;
# all parsing, persistence, review decisions, and record operations remain bound
# to the existing application methods above.
COLORS.update(
    {
        "canvas": "#F2F2EE",
        "paper": "#FFFFFF",
        "white": "#FFFFFF",
        "frost": "#EDEDE8",
        "panel_alt": "#E7E7E1",
        "line": "#D8D8D1",
        "ink": "#161616",
        "hero_text": "#111111",
        "hero_muted": "#62625D",
        "muted": "#71716B",
        "sidebar": "#111111",
        "sidebar_panel": "#111111",
        "navy": "#111111",
        "navy_2": "#202020",
        "orange": "#DFFF00",
        "accent_soft": "#E8FF69",
        "teal": "#315C48",
        "teal_2": "#244637",
        "red": "#A33E32",
    }
)


def button(parent, text: str, command, kind: str = "secondary") -> tk.Button:
    palette = {
        "primary": (COLORS["orange"], COLORS["ink"], "#C9E800"),
        "secondary": (COLORS["frost"], COLORS["ink"], COLORS["panel_alt"]),
        "nav": (COLORS["sidebar"], "#B9B9B2", "#242424"),
        "teal": (COLORS["ink"], COLORS["white"], "#2B2B2B"),
        "danger": ("#F0E2DF", "#873B32", "#E8D4D0"),
    }
    background, foreground, active = palette[kind]
    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=background,
        fg=foreground,
        activebackground=active,
        activeforeground=foreground,
        relief="flat",
        bd=0,
        highlightthickness=0,
        padx=20,
        pady=11,
        font=("Microsoft YaHei UI", 9, "bold"),
        cursor="hand2",
    )


def _surface(parent: tk.Widget, tone: str = "paper", *, border: str | None = None) -> tk.Frame:
    color_map = {
        "paper": COLORS["paper"],
        "panel": COLORS["panel_alt"],
        "canvas": COLORS["canvas"],
        "sidebar": COLORS["sidebar_panel"],
        "frost": COLORS["frost"],
    }
    bg = color_map.get(tone, COLORS["paper"])
    # Surfaces are separated by tone and spacing; borders are reserved for
    # explicit focus/error states rather than routine layout grouping.
    return tk.Frame(parent, bg=bg, highlightthickness=0, bd=0)


def _soft_entry(parent: tk.Widget, *, textvariable=None, width: int = 24) -> tk.Entry:
    return tk.Entry(
        parent,
        textvariable=textvariable,
        width=width,
        bg=COLORS["frost"],
        fg=COLORS["ink"],
        insertbackground=COLORS["ink"],
        relief="flat",
        highlightbackground=COLORS["frost"],
        highlightcolor=COLORS["ink"],
        highlightthickness=1,
        font=("Microsoft YaHei UI", 10),
    )


def _soft_text(parent: tk.Widget, *, height: int = 4, wrap: str = "word") -> tk.Text:
    return tk.Text(
        parent,
        height=height,
        wrap=wrap,
        bg=COLORS["frost"],
        fg=COLORS["ink"],
        insertbackground=COLORS["ink"],
        selectbackground=COLORS["accent_soft"],
        selectforeground=COLORS["ink"],
        relief="flat",
        highlightbackground=COLORS["frost"],
        highlightcolor=COLORS["ink"],
        highlightthickness=1,
        padx=18,
        pady=16,
        font=("Microsoft YaHei UI", 10),
    )


def _pill(parent: tk.Widget, text: str, *, tone: str = "muted") -> tk.Label:
    tones = {
        "muted": (COLORS["panel_alt"], COLORS["muted"]),
        "accent": (COLORS["orange"], COLORS["ink"]),
        "dark": (COLORS["ink"], COLORS["white"]),
        "success": ("#DDE8DF", COLORS["teal"]),
        "danger": ("#F0E2DF", "#873B32"),
    }
    bg, fg = tones.get(tone, tones["muted"])
    return tk.Label(parent, text=text, bg=bg, fg=fg, padx=10, pady=4, font=("Microsoft YaHei UI", 8, "bold"))


def _nike_configure_styles(self) -> None:
    _editorial_configure_styles(self)
    self.style.configure(
        "Treeview",
        background=COLORS["paper"],
        fieldbackground=COLORS["paper"],
        foreground=COLORS["ink"],
        rowheight=36,
        borderwidth=0,
    )
    self.style.configure(
        "Treeview.Heading",
        background=COLORS["ink"],
        foreground=COLORS["white"],
        relief="flat",
        padding=(12, 11),
    )
    self.style.map("Treeview", background=[("selected", COLORS["accent_soft"])], foreground=[("selected", COLORS["ink"])])
    self.style.configure("TScrollbar", background="#C7C7C0", troughcolor=COLORS["canvas"], borderwidth=0, arrowsize=12)


def _nike_show_page(self, name: str) -> None:
    self.pages[name].tkraise()
    for page_name, nav_button in getattr(self, "nav_buttons", {}).items():
        selected = page_name == name
        nav_button.configure(
            bg=COLORS["orange"] if selected else COLORS["sidebar"],
            fg=COLORS["ink"] if selected else "#B9B9B2",
            activebackground=COLORS["accent_soft"] if selected else "#242424",
            activeforeground=COLORS["ink"] if selected else COLORS["white"],
        )
    if name == "Data Check":
        self.refresh_data_check()


def _nike_page_shell(self, name: str, title: str, subtitle: str) -> tk.Frame:
    page = tk.Frame(self.content, bg=COLORS["canvas"])
    page.grid(row=0, column=0, sticky="nsew")
    page.rowconfigure(1, weight=1)
    page.columnconfigure(0, weight=1)
    header = tk.Frame(page, bg=COLORS["canvas"])
    header.grid(row=0, column=0, sticky="ew", padx=42, pady=(30, 18))
    header.columnconfigure(0, weight=1)
    lead = tk.Frame(header, bg=COLORS["canvas"])
    lead.grid(row=0, column=0, sticky="w")
    tk.Label(lead, text=name.upper(), bg=COLORS["canvas"], fg=COLORS["muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
    tk.Label(lead, text=title, bg=COLORS["canvas"], fg=COLORS["hero_text"], font=("Arial", 32, "bold")).pack(anchor="w", pady=(2, 6))
    tk.Label(
        lead,
        text=subtitle,
        bg=COLORS["canvas"],
        fg=COLORS["hero_muted"],
        wraplength=830,
        justify="left",
        font=("Microsoft YaHei UI", 9),
    ).pack(anchor="w")
    mark = tk.Frame(header, bg=COLORS["orange"], width=74, height=8)
    mark.grid(row=0, column=1, sticky="ne", pady=(10, 0))
    mark.grid_propagate(False)
    self.pages[name] = page
    return page


def _nike_build(self) -> None:
    _ensure_visual_assets(self)
    self.configure(bg=COLORS["canvas"])
    self.rowconfigure(0, weight=1)
    self.columnconfigure(1, weight=1)

    sidebar = tk.Frame(self, bg=COLORS["sidebar"], width=226)
    sidebar.grid(row=0, column=0, sticky="ns")
    sidebar.grid_propagate(False)

    brand = tk.Frame(sidebar, bg=COLORS["sidebar"])
    brand.pack(fill="x", padx=24, pady=(30, 34))
    tk.Label(brand, text="FL", bg=COLORS["sidebar"], fg=COLORS["orange"], font=("Arial", 28, "bold")).pack(anchor="w")
    tk.Label(brand, text="FITNESS\nLEDGER", bg=COLORS["sidebar"], fg=COLORS["white"], justify="left", font=("Arial", 16, "bold")).pack(anchor="w", pady=(10, 0))
    tk.Label(brand, text="MOVE. RECORD. KNOW.", bg=COLORS["sidebar"], fg="#74746F", font=("Segoe UI", 7, "bold")).pack(anchor="w", pady=(8, 0))

    nav_wrap = tk.Frame(sidebar, bg=COLORS["sidebar"])
    nav_wrap.pack(fill="x", padx=14)
    self.nav_buttons = {}
    labels = {
        "Quick Entry": "01  QUICK ENTRY",
        "Body": "02  BODY",
        "Diet": "03  DIET",
        "Training": "04  TRAINING",
        "Movement Progress": "05  MOVEMENT",
        "Data Check": "06  DATA CHECK",
    }
    for name, label in labels.items():
        nav_button = button(nav_wrap, label, lambda page=name: self.show_page(page), "nav")
        nav_button.configure(anchor="w", padx=15, pady=12, font=("Segoe UI", 8, "bold"))
        nav_button.pack(fill="x", pady=2)
        self.nav_buttons[name] = nav_button

    tk.Frame(sidebar, bg=COLORS["sidebar"]).pack(fill="both", expand=True)
    footer = tk.Frame(sidebar, bg=COLORS["sidebar"])
    footer.pack(fill="x", padx=24, pady=(0, 26))
    tk.Frame(footer, bg="#343432", height=1).pack(fill="x", pady=(0, 16))
    tk.Label(footer, text="LOCAL-FIRST / PRIVATE", bg=COLORS["sidebar"], fg=COLORS["orange"], font=("Segoe UI", 7, "bold")).pack(anchor="w")
    tk.Label(footer, text="Atomic saves · automatic backups", bg=COLORS["sidebar"], fg="#74746F", font=("Microsoft YaHei UI", 7)).pack(anchor="w", pady=(5, 0))

    self.content = tk.Frame(self, bg=COLORS["canvas"])
    self.content.grid(row=0, column=1, sticky="nsew")
    self.content.rowconfigure(0, weight=1)
    self.content.columnconfigure(0, weight=1)
    self.build_quick_entry()
    self.build_body_page()
    self.build_diet_page()
    self.build_training_page()
    self.build_movement_page()
    self.build_data_check_page()


def _nike_build_quick_entry(self) -> None:
    page = self.page_shell(
        "Quick Entry",
        "Daily Capture",
        "One unfiltered daily note becomes a reviewable body, nutrition, cardio, and training record.",
    )
    body = tk.Frame(page, bg=COLORS["canvas"])
    body.grid(row=1, column=0, sticky="nsew", padx=42, pady=(0, 30))
    body.rowconfigure(0, weight=1)
    body.columnconfigure(0, weight=3)
    body.columnconfigure(1, weight=2)

    editor = tk.Frame(body, bg=COLORS["paper"])
    editor.grid(row=0, column=0, sticky="nsew")
    editor.rowconfigure(2, weight=1)
    editor.columnconfigure(0, weight=1)
    tk.Label(editor, text="WRITE THE DAY", bg=COLORS["paper"], fg=COLORS["ink"], font=("Segoe UI", 8, "bold")).grid(row=0, column=0, sticky="w", padx=30, pady=(26, 5))
    tk.Label(editor, text="Raw first. Structure second.", bg=COLORS["paper"], fg=COLORS["hero_text"], font=("Arial", 21, "bold")).grid(row=1, column=0, sticky="w", padx=30)
    self.raw_text = _soft_text(editor, height=22)
    self.raw_text.grid(row=2, column=0, sticky="nsew", padx=30, pady=(18, 18))
    self.raw_text.configure(font=("Microsoft YaHei UI", 12), bg="#F4F4F0", highlightbackground="#F4F4F0")
    actions = tk.Frame(editor, bg=COLORS["paper"])
    actions.grid(row=3, column=0, sticky="ew", padx=30, pady=(0, 12))
    actions.columnconfigure(0, weight=1)
    button(actions, "PARSE & REVIEW  →", self.parse_and_review, "primary").grid(row=0, column=0, sticky="ew")
    button(actions, "Undo last save", self.undo_last_save, "secondary").grid(row=0, column=1, padx=(10, 0))
    self.quick_status = tk.StringVar(value="Ready for a new daily entry.")
    tk.Label(editor, textvariable=self.quick_status, bg=COLORS["paper"], fg=COLORS["muted"], justify="left", wraplength=780, font=("Microsoft YaHei UI", 8)).grid(row=4, column=0, sticky="ew", padx=30, pady=(0, 24))

    aside = tk.Frame(body, bg=COLORS["canvas"])
    aside.grid(row=0, column=1, sticky="nsew", padx=(28, 0))
    aside.rowconfigure(1, weight=1)
    aside.columnconfigure(0, weight=1)
    overview = tk.Frame(aside, bg=COLORS["ink"])
    overview.grid(row=0, column=0, sticky="ew", pady=(0, 22))
    tk.Label(overview, text="TODAY / STATUS", bg=COLORS["ink"], fg=COLORS["orange"], font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=22, pady=(20, 7))
    self.today_status_title = tk.StringVar(value="No records yet")
    tk.Label(overview, textvariable=self.today_status_title, bg=COLORS["ink"], fg=COLORS["white"], font=("Arial", 17, "bold")).pack(anchor="w", padx=22)
    self.today_status_text = tk.StringVar(value="Save your first entry to surface the daily state here.")
    tk.Label(overview, textvariable=self.today_status_text, bg=COLORS["ink"], fg="#C6C6BF", justify="left", wraplength=300, font=("Microsoft YaHei UI", 9)).pack(anchor="w", fill="x", padx=22, pady=(10, 22))

    recent = tk.Frame(aside, bg=COLORS["canvas"])
    recent.grid(row=1, column=0, sticky="nsew")
    recent.rowconfigure(1, weight=1)
    recent.columnconfigure(0, weight=1)
    head = tk.Frame(recent, bg=COLORS["canvas"])
    head.grid(row=0, column=0, sticky="ew", pady=(0, 10))
    tk.Label(head, text="RECENT SAVED", bg=COLORS["canvas"], fg=COLORS["ink"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
    tk.Label(head, text="Direct routes back into the last three records.", bg=COLORS["canvas"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 8)).pack(anchor="w", pady=(4, 0))
    self.recent_records_frame = tk.Frame(recent, bg=COLORS["canvas"])
    self.recent_records_frame.grid(row=1, column=0, sticky="nsew")
    self.recent_records_frame.columnconfigure(0, weight=1)


FitnessTrackerApp.configure_styles = _nike_configure_styles
FitnessTrackerApp.page_shell = _nike_page_shell
FitnessTrackerApp.build = _nike_build
FitnessTrackerApp.build_quick_entry = _nike_build_quick_entry
FitnessTrackerApp.show_page = _nike_show_page


# Premium lifestyle presentation layer. It preserves every existing control and
# delegates all behavior to the established application methods.
HERO_ART_FILE = BASE_DIR / "assets" / "fitness-ledger-hero-v2.png"
BADGE_ART_FILE = BASE_DIR / "assets" / "fitness-ledger-monogram-v3.png"
ICON_FILE = BASE_DIR / "assets" / "fitness-ledger-monogram-v3.ico"
ICON_PNG = BASE_DIR / "assets" / "fitness-ledger-monogram-v3.png"

COLORS.update(
    {
        "canvas": "#F5F1E8",
        "paper": "#FCF8F0",
        "white": "#FFFFFF",
        "frost": "#F7F2E8",
        "panel_alt": "#F0E9DD",
        "line": "#D7CDBC",
        "shadow": "#D4C7B6",
        "ink": "#12110F",
        "hero_text": "#111111",
        "hero_muted": "#6C675F",
        "muted": "#6B645A",
        "sidebar": "#111211",
        "sidebar_panel": "#191A18",
        "orange": "#E0BD1F",
        "accent_soft": "#E7D1A0",
    }
)


def _premium_ensure_visual_assets(self) -> None:
    if getattr(self, "_premium_visual_assets_ready", False):
        return
    self.hero_art = _load_scaled_photo(HERO_ART_FILE, 1680, 560)
    self.brand_badge = _load_scaled_photo(BADGE_ART_FILE, 96, 96)
    self.brand_badge_small = _load_scaled_photo(BADGE_ART_FILE, 48, 48)
    self._premium_visual_assets_ready = True


def button(parent, text: str, command, kind: str = "secondary") -> tk.Button:
    palette = {
        "primary": (COLORS["orange"], COLORS["ink"], "#CBE900"),
        "secondary": (COLORS["paper"], COLORS["ink"], COLORS["panel_alt"]),
        "nav": (COLORS["sidebar"], "#B8B8B2", "#272826"),
        "teal": (COLORS["ink"], COLORS["white"], "#30312F"),
        "danger": ("#F2E6E3", "#873C33", "#E9D7D3"),
    }
    background, foreground, active = palette[kind]
    widget = tk.Button(
        parent,
        text=text,
        command=command,
        bg=background,
        fg=foreground,
        activebackground=active,
        activeforeground=foreground,
        relief="flat",
        bd=0,
        highlightbackground=COLORS["line"] if kind == "secondary" else background,
        highlightcolor=COLORS["ink"],
        highlightthickness=1 if kind == "secondary" else 0,
        padx=20,
        pady=11,
        font=("Microsoft YaHei UI", 9, "bold"),
        cursor="hand2",
    )

    def enter(_event=None) -> None:
        if str(widget.cget("state")) != "disabled":
            widget.configure(bg=active)

    def leave(_event=None) -> None:
        if str(widget.cget("state")) != "disabled":
            if getattr(widget, "_nav_selected", False):
                widget.configure(bg=COLORS["orange"], fg=COLORS["ink"])
            else:
                widget.configure(bg=background, fg=foreground)

    widget.bind("<Enter>", enter, add="+")
    widget.bind("<Leave>", leave, add="+")
    return widget


def _surface(parent: tk.Widget, tone: str = "paper", *, border: str | None = None) -> tk.Frame:
    color_map = {
        "paper": COLORS["paper"],
        "panel": COLORS["panel_alt"],
        "canvas": COLORS["canvas"],
        "sidebar": COLORS["sidebar_panel"],
        "frost": COLORS["frost"],
    }
    bg = color_map.get(tone, COLORS["paper"])
    return tk.Frame(
        parent,
        bg=bg,
        highlightbackground=border or COLORS["line"],
        highlightthickness=1 if tone in {"paper", "frost", "panel"} else 0,
        bd=0,
    )


def _premium_configure_styles(self) -> None:
    _nike_configure_styles(self)
    self.style.configure("TScrollbar", background="#C8C7C1", troughcolor=COLORS["canvas"], borderwidth=0, arrowsize=11)
    self.style.configure(
        "TCombobox",
        fieldbackground=COLORS["frost"],
        background=COLORS["frost"],
        foreground=COLORS["ink"],
        bordercolor=COLORS["line"],
        lightcolor=COLORS["line"],
        darkcolor=COLORS["line"],
        arrowsize=12,
        padding=7,
    )


def _premium_page_shell(self, name: str, title: str, subtitle: str) -> tk.Frame:
    page = tk.Frame(self.content, bg=COLORS["canvas"])
    page.grid(row=0, column=0, sticky="nsew")
    page.rowconfigure(1, weight=1)
    page.columnconfigure(0, weight=1)

    hero_height = 224 if name == "Quick Entry" else 170
    hero = tk.Canvas(page, height=hero_height, bg="#171816", highlightthickness=0, bd=0)
    hero.grid(row=0, column=0, sticky="ew")

    def paint(event=None) -> None:
        width = max(hero.winfo_width(), 1) if event is None else max(event.width, 1)
        hero.delete("all")
        if getattr(self, "hero_art", None):
            hero.create_image(0, hero_height // 2, image=self.hero_art, anchor="w")
        hero.create_rectangle(0, 0, min(610, width), hero_height, fill="#111211", stipple="gray25", outline="")
        hero.create_text(48, 45, text=name.upper(), anchor="nw", fill="#D8D8D2", font=("Segoe UI", 8, "bold"))
        hero.create_text(46, 72, text=title, anchor="nw", fill="#FFFFFF", font=("Arial", 30, "bold"))
        hero.create_text(
            48,
            124,
            text=subtitle,
            anchor="nw",
            width=min(480, max(width - 96, 240)),
            fill="#C4C4BE",
            font=("Microsoft YaHei UI", 9),
        )
        hero.create_rectangle(48, hero_height - 35, 122, hero_height - 31, fill=COLORS["orange"], outline="")

    hero.bind("<Configure>", paint)
    page.premium_hero = hero
    self.pages[name] = page
    return page


def _premium_mousewheel(self, event) -> str | None:
    """Route the wheel to the scrollable widget currently under the pointer."""
    widget = self.winfo_containing(event.x_root, event.y_root)
    while widget is not None:
        if hasattr(widget, "yview_scroll"):
            try:
                direction = -1 if event.delta > 0 else 1
                widget.yview_scroll(direction, "units")
                return "break"
            except (tk.TclError, AttributeError):
                pass
        widget = getattr(widget, "master", None)
    return None


def _premium_build(self) -> None:
    _premium_ensure_visual_assets(self)
    self.geometry("1420x860+25+25")
    self.minsize(1120, 700)
    self.configure(bg=COLORS["canvas"])
    self.rowconfigure(0, weight=1)
    self.columnconfigure(1, weight=1)

    sidebar = tk.Frame(self, bg=COLORS["sidebar"], width=226)
    sidebar.grid(row=0, column=0, sticky="ns")
    sidebar.grid_propagate(False)
    brand = tk.Frame(sidebar, bg=COLORS["sidebar"])
    brand.pack(fill="x", padx=26, pady=(28, 34))
    if getattr(self, "brand_badge_small", None):
        tk.Label(brand, image=self.brand_badge_small, bg=COLORS["sidebar"]).pack(anchor="w")
    tk.Label(brand, text="FITNESS\nLEDGER", bg=COLORS["sidebar"], fg=COLORS["white"], justify="left", font=("Arial", 15, "bold")).pack(anchor="w", pady=(10, 0))
    tk.Label(brand, text="MOVE. RECORD. KNOW.", bg=COLORS["sidebar"], fg="#74746F", font=("Segoe UI", 7, "bold")).pack(anchor="w", pady=(8, 0))

    nav_wrap = tk.Frame(sidebar, bg=COLORS["sidebar"])
    nav_wrap.pack(fill="x", padx=14)
    self.nav_buttons = {}
    labels = {
        "Quick Entry": "01   QUICK ENTRY",
        "Body": "02   BODY",
        "Diet": "03   DIET",
        "Training": "04   TRAINING",
        "Movement Progress": "05   MOVEMENT",
        "Data Check": "06   DATA CHECK",
    }
    for name, label in labels.items():
        nav_button = button(nav_wrap, label, lambda page=name: self.show_page(page), "nav")
        nav_button.configure(anchor="w", padx=17, pady=13, font=("Segoe UI", 8, "bold"), highlightthickness=0)
        nav_button.pack(fill="x", pady=2)
        self.nav_buttons[name] = nav_button

    tk.Frame(sidebar, bg=COLORS["sidebar"]).pack(fill="both", expand=True)
    footer = tk.Frame(sidebar, bg=COLORS["sidebar"])
    footer.pack(fill="x", padx=26, pady=(0, 26))
    tk.Frame(footer, bg="#3A3B38", height=1).pack(fill="x", pady=(0, 16))
    tk.Label(footer, text="LOCAL-FIRST / PRIVATE", bg=COLORS["sidebar"], fg=COLORS["orange"], font=("Segoe UI", 7, "bold")).pack(anchor="w")
    tk.Label(footer, text="Atomic saves · automatic backups", bg=COLORS["sidebar"], fg="#74746F", font=("Microsoft YaHei UI", 7)).pack(anchor="w", pady=(6, 0))

    self.content = tk.Frame(self, bg=COLORS["canvas"])
    self.content.grid(row=0, column=1, sticky="nsew")
    self.content.rowconfigure(0, weight=1)
    self.content.columnconfigure(0, weight=1)
    self.bind_all("<MouseWheel>", self._premium_mousewheel, add="+")
    self.build_quick_entry()
    self.build_body_page()
    self.build_diet_page()
    self.build_training_page()
    self.build_movement_page()
    self.build_data_check_page()
    self.after_idle(lambda: (self.state("zoomed"), self.show_page("Quick Entry")))


def _premium_build_quick_entry(self) -> None:
    page = self.page_shell(
        "Quick Entry",
        "Daily Capture",
        "One unfiltered daily note becomes a reviewable body, nutrition, cardio, and training record.",
    )
    page.rowconfigure(1, weight=1)
    page.columnconfigure(0, weight=1)
    body = tk.Frame(page, bg=COLORS["canvas"])
    self.quick_body = body
    body.grid(row=1, column=0, sticky="nsew", padx=34, pady=(22, 28))
    body.rowconfigure(0, weight=1)
    body.columnconfigure(0, weight=1)
    body.columnconfigure(1, weight=0, minsize=350)

    editor_shadow = tk.Frame(body, bg=COLORS["shadow"])
    editor_shadow.grid(row=0, column=0, sticky="nsew", padx=(0, 3), pady=(0, 3))
    editor_shadow.rowconfigure(0, weight=1)
    editor_shadow.columnconfigure(0, weight=1)
    editor = tk.Frame(editor_shadow, bg=COLORS["paper"], highlightbackground=COLORS["line"], highlightthickness=1)
    self.quick_editor = editor
    editor.grid(row=0, column=0, sticky="nsew", padx=(0, 3), pady=(0, 3))
    editor.rowconfigure(2, weight=1)
    editor.columnconfigure(0, weight=1)
    tk.Label(editor, text="WRITE THE DAY", bg=COLORS["paper"], fg=COLORS["ink"], font=("Segoe UI", 8, "bold")).grid(row=0, column=0, sticky="w", padx=30, pady=(26, 5))
    tk.Label(editor, text="Raw first. Structure second.", bg=COLORS["paper"], fg=COLORS["hero_text"], font=("Arial", 20, "bold")).grid(row=1, column=0, sticky="w", padx=30)
    self.raw_text = _soft_text(editor, height=13)
    self.raw_text.grid(row=2, column=0, sticky="nsew", padx=30, pady=(18, 18))
    self.raw_text.configure(width=1, font=("Microsoft YaHei UI", 11), bg="#FAF7EF", highlightbackground=COLORS["line"])
    actions = tk.Frame(editor, bg=COLORS["paper"])
    actions.grid(row=3, column=0, sticky="ew", padx=30, pady=(0, 14))
    actions.columnconfigure(0, weight=1)
    button(actions, "PARSE & REVIEW   →", self.parse_and_review, "primary").grid(row=0, column=0, sticky="ew")
    button(actions, "Undo last save", self.undo_last_save, "secondary").grid(row=0, column=1, padx=(10, 0))
    self.quick_status = tk.StringVar(value="Ready for a new daily entry.")
    tk.Label(editor, textvariable=self.quick_status, bg=COLORS["paper"], fg=COLORS["muted"], justify="center", wraplength=760, font=("Microsoft YaHei UI", 8)).grid(row=4, column=0, sticky="ew", padx=30, pady=(0, 22))

    aside = tk.Frame(body, bg=COLORS["canvas"], width=350)
    self.quick_aside = aside
    aside.grid(row=0, column=1, sticky="nsew", padx=(24, 0))
    aside.grid_propagate(False)
    aside.rowconfigure(0, weight=1)
    aside.columnconfigure(0, weight=1)

    overview = tk.Frame(page, bg="#171816", highlightbackground="#363733", highlightthickness=1)
    overview.place(relx=1.0, x=-18, y=18, width=280, height=168, anchor="ne")
    tk.Label(overview, text="TODAY / STATUS", bg="#171816", fg=COLORS["orange"], font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=22, pady=(20, 7))
    self.today_status_title = tk.StringVar(value="No records yet")
    tk.Label(overview, textvariable=self.today_status_title, bg="#171816", fg=COLORS["white"], font=("Arial", 17, "bold")).pack(anchor="w", padx=22)
    self.today_status_text = tk.StringVar(value="Save your first entry to surface the daily state here.")
    tk.Label(overview, textvariable=self.today_status_text, bg="#171816", fg="#C8C8C1", justify="left", wraplength=330, font=("Microsoft YaHei UI", 9)).pack(anchor="w", fill="x", padx=22, pady=(10, 22))

    recent = tk.Frame(aside, bg=COLORS["canvas"])
    recent.grid(row=0, column=0, sticky="nsew")
    recent.rowconfigure(1, weight=1)
    recent.columnconfigure(0, weight=1)
    head = tk.Frame(recent, bg=COLORS["canvas"])
    head.grid(row=0, column=0, sticky="ew", pady=(0, 10))
    tk.Label(head, text="RECENT SAVED", bg=COLORS["canvas"], fg=COLORS["ink"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
    tk.Label(head, text="Direct routes back into the last three records.", bg=COLORS["canvas"], fg=COLORS["muted"], font=("Microsoft YaHei UI", 8)).pack(anchor="w", pady=(4, 0))
    self.recent_records_frame = tk.Frame(recent, bg=COLORS["canvas"])
    self.recent_records_frame.grid(row=1, column=0, sticky="nsew")
    self.recent_records_frame.columnconfigure(0, weight=1)


def _build_stream_page(self, name: str, title: str, subtitle: str) -> tuple[tk.Frame, tk.Frame]:
    page = self.page_shell(name, title, subtitle)
    shadow = tk.Frame(page, bg=COLORS["shadow"])
    shadow.grid(row=1, column=0, sticky="nsew", padx=38, pady=(22, 28))
    shadow.rowconfigure(0, weight=1)
    shadow.columnconfigure(0, weight=1)
    shell = _surface(shadow, "paper")
    shell.grid(row=0, column=0, sticky="nsew", padx=(0, 3), pady=(0, 3))
    shell.rowconfigure(1, weight=1)
    shell.columnconfigure(0, weight=1)
    return page, shell


FitnessTrackerApp.configure_styles = _premium_configure_styles
FitnessTrackerApp.page_shell = _premium_page_shell
FitnessTrackerApp.build = _premium_build
FitnessTrackerApp.build_quick_entry = _premium_build_quick_entry
FitnessTrackerApp._premium_mousewheel = _premium_mousewheel


def _premium_show_page(self, name: str) -> None:
    if name == "Movement Progress" and hasattr(self, "command_service"):
        self.database, self.movement_dictionary = self.command_service.load_state()
        self.movement_definitions_by_id, self.movement_definitions_by_alias = movement_definition_index(
            self.movement_dictionary
        )
        self.refresh_movements()
    self.pages[name].tkraise()
    for page_name, nav_button in getattr(self, "nav_buttons", {}).items():
        selected = page_name == name
        nav_button._nav_selected = selected
        nav_button.configure(
            bg=COLORS["orange"] if selected else COLORS["sidebar"],
            fg=COLORS["ink"] if selected else "#B8B8B2",
            activebackground=COLORS["accent_soft"] if selected else "#272826",
            activeforeground=COLORS["ink"] if selected else COLORS["white"],
        )
    if name == "Data Check":
        self.refresh_data_check()


FitnessTrackerApp.show_page = _premium_show_page


def _shared_reload_state(self) -> None:
    self.database, self.movement_dictionary = self.command_service.load_state()
    self.movement_definitions_by_id, self.movement_definitions_by_alias = movement_definition_index(
        self.movement_dictionary
    )


def _shared_save_movement_definition(self, movement: dict | None, definition: dict, values: dict) -> bool:
    movement_id = str(definition.get("movement_id", ""))
    try:
        result = self.command_service.update_movement_definition(movement_id, values)
    except LedgerCommandError as exc:
        messagebox.showerror("无法保存动作词典", str(exc))
        return False
    _shared_reload_state(self)
    self.refresh_all()
    restored = sum(int(result.get("reconciliation", {}).get(key, 0)) for key in ("merged_history", "restored_skipped"))
    if restored:
        self.quick_status.set(f"已归并 {restored} 条历史记录。")
    return True


def _shared_toggle_movement_definition(self, definition: dict) -> bool:
    next_active = not bool(definition.get("active", True))
    try:
        self.command_service.set_movement_active(
            str(definition.get("movement_id", "")), next_active
        )
    except LedgerCommandError as exc:
        messagebox.showerror("无法更新动作状态", str(exc))
        return False
    definition["active"] = next_active
    _shared_reload_state(self)
    self.refresh_all()
    return True


def _shared_delete_movement_definition(self, movement_id: str) -> bool:
    definition = self.movement_definitions_by_id.get(str(movement_id))
    if not definition:
        messagebox.showerror("无法删除", "找不到动作词典条目。")
        return False
    try:
        self.command_service.delete_movement_definition(
            str(movement_id), str(definition.get("display_name", ""))
        )
    except LedgerCommandError as exc:
        messagebox.showerror("无法删除", str(exc))
        return False
    _shared_reload_state(self)
    self.refresh_all()
    return True


def _shared_safe_close(self) -> None:
    # Every user mutation is already persisted. Rewriting stale in-memory state here
    # could overwrite changes made by the Web process while the desktop app was open.
    backup_data()
    self.destroy()


FitnessTrackerApp.save_movement_definition = _shared_save_movement_definition
FitnessTrackerApp.toggle_movement_definition = _shared_toggle_movement_definition
FitnessTrackerApp.delete_movement_definition = _shared_delete_movement_definition
FitnessTrackerApp.close = _shared_safe_close


def format_set_summary(record: dict) -> str:
    sets = record.get("sets") or []
    if sets:
        return ", ".join(
            f"{format_set_weight(item)}×{format_number(item.get('reps'))}×{format_number(item.get('sets'))}"
            for item in sets
        )

    cardio = record.get("cardio") or {}
    cardio_parts = []
    if cardio.get("duration_minutes") is not None:
        cardio_parts.append(f"{format_number(cardio['duration_minutes'])}min")
    if cardio.get("heart_rate") is not None:
        cardio_parts.append(f"HR{format_number(cardio['heart_rate'])}")
    if cardio.get("incline") is not None:
        cardio_parts.append(f"incline {format_number(cardio['incline'])}")
    if cardio.get("speed") is not None:
        cardio_parts.append(f"speed {format_number(cardio['speed'])}")
    return " ".join(cardio_parts) or str(record.get("raw", "")).strip()


def main() -> None:
    app = FitnessTrackerApp()
    if os.environ.get("FITNESS_LEDGER_SMOKE_TEST") == "1":
        app.withdraw()
        app.after(500, app.destroy)
    app.mainloop()


if __name__ == "__main__":
    main()
