import json
import re
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "tracker.json"
DICTIONARY = ROOT / "data" / "movement_dictionary.json"
BACKUPS = ROOT / "data" / "backups"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: dict) -> None:
    temp = path.with_name(f"{path.name}.tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    json.loads(temp.read_text(encoding="utf-8"))
    temp.replace(path)


def backup(path: Path) -> Path:
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = BACKUPS / f"{path.stem}_{stamp}{path.suffix}"
    shutil.copy2(path, target)
    return target


def recover_numbered_movement_notes(raw: str) -> dict[int, str]:
    notes = {}
    current_order = None
    for line in str(raw or "").splitlines():
        stripped = line.strip()
        order_match = re.match(r"^(\d+)\s*[.、)]\s*", stripped)
        if order_match:
            current_order = int(order_match.group(1))
            continue
        note_match = re.match(r"^(?:notes?|备注)\s*[:：]\s*(.+)$", stripped, re.I)
        if current_order is not None and note_match:
            notes[current_order] = note_match.group(1).strip()
    return notes


training_translations = {
    1: ("肩部", "反向飞鸟作为独立动作记录；哑铃飞鸟略有控制。"),
    2: ("背部", "引体向上为热身动作。"),
    3: ("胸部 / 肩部", "Y举的动作感受很好。"),
    4: ("背部 / 腿部", "训练期间接听电话，整体训练质量偏低。"),
    5: ("步行 / 无力量训练", "低强度活动日。"),
    6: ("肩部", "器械飞鸟和器械推肩与龙门架飞鸟、悍马推肩分别记录。"),
    7: ("背部", "左肘不适，因此调整了弯举位置。"),
    8: ("胸部 / 肩部", "本次训练不包含后束和手臂动作。"),
    9: ("肩部 / 腿部（后束侧重）", "后束侧重训练日。"),
    10: ("背部 / 腹部", "力量训练后明确记录了有氧。"),
    11: ("胸部 / 腿部", ""),
}

body_translations = {
    "2026-06-15": ("首次身体成分记录", "力量训练 + 有氧", "晚间称重，与次日晨间数据不可直接比较。"),
    "2026-06-16": ("背部 + 有氧", "跑步机爬坡", "晨起空腹，与 2026-06-15 18:07 的测量条件不同。"),
    "2026-06-17": ("胸部 + 肩部 + 有氧", "跑步机爬坡", "体脂秤数据仅作参考。"),
    "2026-06-18": ("背部 + 腿部 + 有氧", "跑步机爬坡", "体脂秤数据仅作参考。"),
    "2026-06-19": ("步行 / 无力量训练", "步行", "约 1 至 2 小时、12000 步；非力量训练日。"),
    "2026-06-20": ("肩部 / 股四头肌 + 有氧", "跑步机爬坡", "晨起空腹，仅作参考。"),
    "2026-06-21": ("背部 + 有氧", "跑步机爬坡", "晨起空腹；体脂秤数据仅作参考。"),
    "2026-06-22": ("胸部", "", "仅体重数据相对可靠，其他数值仅作参考。"),
    "2026-06-23": ("肩部 / 腿部（后束侧重）", "", "晨起空腹；体脂秤数据仅作参考。"),
    "2026-06-24": ("背部 / 腹部 + 跑步机有氧", "跑步机", "晨起空腹；体脂秤数据仅作参考。"),
}


tracker = read(DATA)
dictionary = read(DICTIONARY)
tracker_backup = backup(DATA)
dictionary_backup = backup(DICTIONARY)

definitions = {
    item.get("movement_id"): item
    for item in dictionary.get("movements", [])
    if item.get("movement_id")
}

sessions_by_day = {}
for session in tracker.get("training_sessions", []):
    try:
        day = int(session.get("No."))
    except (TypeError, ValueError):
        continue
    sessions_by_day[day] = session
    translated = training_translations.get(day)
    if translated:
        split, notes = translated
        if session.get("Split") != split and session.get("Split") and not session.get("Split Original"):
            session["Split Original"] = session.get("Split")
        if session.get("Notes") != notes and session.get("Notes") and not session.get("Notes Original"):
            session["Notes Original"] = session.get("Notes")
        session["Split"] = split
        session["Notes"] = notes

for record in tracker.get("daily_records", []):
    day = str(record.get("Date", ""))[:10]
    translated = body_translations.get(day)
    if not translated:
        continue
    for field, value in zip(("Training", "Cardio", "Notes"), translated):
        original_field = f"{field} Original"
        if record.get(field) != value and record.get(field) and not record.get(original_field):
            record[original_field] = record.get(field)
        record[field] = value

for record in tracker.get("diet_records", []):
    day = str(record.get("Date", ""))[:10]
    summary = str(record.get("Food Summary", ""))
    translated = summary
    if day == "2026-06-25":
        replacements = {
            "Breakfast": "早餐：",
            "Pre-workout": "练前：",
            "Post-workout": "练后：",
            "Dinner": "晚餐：",
        }
        for source, target in replacements.items():
            translated = translated.replace(source, target)
    translated = re.sub(r"(?im)^\s*\*\s*none\s*$", "* 无", translated)
    if translated != summary:
        if summary and not record.get("Food Summary Original"):
            record["Food Summary Original"] = summary
        record["Food Summary"] = translated

history_by_day = {}
for movement in tracker.get("movements", {}).values():
    movement_id = movement.get("movement_id", "")
    definition = definitions.get(movement_id, {})
    display_name = definition.get("display_name") or movement.get("name", "")
    old_name = movement.get("name", "")
    if display_name and old_name != display_name:
        aliases = movement.setdefault("aliases", [])
        if old_name and old_name not in aliases:
            aliases.append(old_name)
        movement["name"] = display_name
    for history in movement.get("history", []):
        try:
            day = int(history.get("training_day"))
        except (TypeError, ValueError):
            continue
        history_by_day.setdefault(day, []).append((movement, history, display_name))

for day, session in sessions_by_day.items():
    recovered = recover_numbered_movement_notes(session.get("Raw Record", ""))
    note_parts = []
    for _movement, history, display_name in sorted(
        history_by_day.get(day, []), key=lambda item: int(item[1].get("order") or 0)
    ):
        order = int(history.get("order") or 0)
        if not str(history.get("notes", "")).strip() and recovered.get(order):
            history["notes"] = recovered[order]
        note = str(history.get("notes", "")).strip()
        if note:
            note_parts.append(f"{display_name}：{note.rstrip('；;。.!！')}")
    if note_parts:
        current_notes = str(session.get("Notes", "")).strip()
        note_summary = f"{'；'.join(note_parts)}。"
        if current_notes and current_notes != note_summary and not session.get("Notes Original"):
            session["Notes Original"] = current_notes
        session["Notes"] = note_summary

write(DATA, tracker)
write(DICTIONARY, dictionary)
print(f"tracker_backup={tracker_backup}")
print(f"dictionary_backup={dictionary_backup}")
print("TRAINING_NOTES_ZH_MIGRATION_OK")
