import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "tracker.json"
DICT = ROOT / "data" / "movement_dictionary.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    temp = path.with_name(f"{path.name}.tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    json.loads(temp.read_text(encoding="utf-8"))
    temp.replace(path)


movement_dictionary = read(DICT)
tracker = read(DATA)

display_updates = {
    "CHEST_001": "诺德士挂片推一",
    "CHEST_002": "诺德士挂片推二",
    "CHEST_003": "诺德士挂片推三",
    "CHEST_004": "悍马下斜推",
    "CHEST_005": "龙门架飞鸟",
    "SHOULDER_001": "Y举",
    "SHOULDER_002": "龙门架后束飞鸟",
    "SHOULDER_003": "器械中束飞鸟",
    "SHOULDER_004": "器械反飞",
    "SHOULDER_005": "悍马推肩",
    "SHOULDER_006": "诺德士推肩",
    "SHOULDER_007": "俯身哑铃肩伸",
    "SHOULDER_008": "后束Y举",
    "BACK_001": "引体向上",
    "BACK_002": "诺德士高拉",
    "BACK_003": "龙门架坐划",
    "BACK_004": "悍马拉背一",
    "BACK_005": "悍马拉背二",
    "BACK_006": "悍马拉背三",
    "BACK_007": "诺德士拉背拨片",
    "BACK_008": "龙门架高拉",
    "ARM_001": "肩伸位二头弯举",
    "ARM_002": "肩屈位二头弯举",
    "ARM_003": "器械三头下压",
    "ARM_004": "绳索三头下压",
    "LEG_001": "腿屈伸",
    "LEG_002": "腿弯举",
    "CORE_001": "鹦鹉螺卷腹",
    "CARDIO_001": "跑步机有氧",
}

alias_additions = {
    "CHEST_003": ["诺德士挂片推三（热身）", "诺德士挂片推三(热身)", "挂片推三"],
    "LEG_001": ["腿屈伸（股四）", "腿屈伸(股四)", "股四腿屈伸"],
    "LEG_002": ["腿屈伸（股二）", "腿屈伸(股二)", "股二腿屈伸"],
    "ARM_004": ["绳索三头下压"],
    "CARDIO_001": ["跑步机", "跑步机有氧"],
}

for movement in movement_dictionary.get("movements", []):
    movement_id = movement.get("movement_id")
    movement["aliases"] = [
        alias
        for alias in movement.get("aliases", [])
        if alias and not set(str(alias)) <= {"?"}
    ]
    if movement_id in display_updates:
        old_display = movement.get("display_name", "")
        old_english = movement.get("english_name", "")
        aliases = movement.setdefault("aliases", [])
        for value in (old_display, old_english):
            if value and value not in aliases:
                aliases.append(value)
        movement["display_name"] = display_updates[movement_id]
    for alias in alias_additions.get(movement_id, []):
        if alias not in movement.setdefault("aliases", []):
            movement["aliases"].append(alias)

known_name_to_id = {
    "诺德士挂片推三（热身）": "CHEST_003",
    "诺德士挂片推三": "CHEST_003",
    "腿屈伸（股四）": "LEG_001",
    "腿屈伸（股二）": "LEG_002",
    "绳索三头下压": "ARM_004",
}

for movement in tracker.get("movements", {}).values():
    target_id = known_name_to_id.get(movement.get("name", ""))
    if not target_id:
        continue
    movement["movement_id"] = target_id
    aliases = movement.setdefault("aliases", [])
    if movement.get("name") not in aliases:
        aliases.append(movement.get("name"))
    for history in movement.get("history") or []:
        history["movement_id"] = target_id

diet_translations = {
    "2026-06-24": (
        "燕麦51g，带皮香蕉约160g，卤鸡腿160g（基本去皮），生鸡胸360g，馒头共210g。",
        "鸡腿按带骨重量估算；营养数据为近似值。",
    ),
    "2026-06-23": (
        "燕麦50g，3个蛋白加1个全蛋，带皮香蕉150g，练后餐来自图片估算，熟米饭160g，生鸡胸360g。",
        "练后餐根据图片估算。",
    ),
    "2026-06-22": (
        "熟红薯240g，3个蛋白，1个全蛋，带皮香蕉150g，卤鸡腿170g（带骨估算），鸡胸260g，圣女果100g。",
        "按全天餐食合并计算。",
    ),
    "2026-06-21": (
        "1个全蛋，2个蛋白，熟红薯约90g，带皮香蕉168g（可食约107g），白米饭190g，三鲜汤1900g。",
        "三鲜汤油脂相对较高。",
    ),
    "2026-06-20": (
        "燕麦50g，1个全蛋加2个蛋白，带皮香蕉168g（可食约107g），土豆牛肉饭180g，鸡胸230g。",
        "训练日；晚餐按默认建议执行。",
    ),
    "2026-06-19": (
        "燕麦50g，熟鸡胸104g，快餐米饭一份，熟鸡胸260g，圣女果100g。",
        "非力量训练日。",
    ),
    "2026-06-18": (
        "燕麦50g，1个全蛋加2个蛋白，烤鸡腿，新疆牛肉拌面约300-320g，鸡胸250g。",
        "训练日。",
    ),
    "2026-06-17": (
        "面条300g，小菜，面包鸡蛋，零食，糯米糕100g，鸡胸300g。",
        "胸肩训练日。",
    ),
    "2026-06-16": (
        "2个全蛋，2个蛋白，燕麦50g，去皮鸭腿，米饼4个（每个35g），酸奶450g。",
        "背腿训练日。",
    ),
    "2026-06-15": (
        "2个全蛋，1个蛋白，燕麦50g，去皮鸭腿2个（约200g可食），牛肉10g，芝士米饼16g，牛肉饼约200g，小鸡胸80g，燕麦20g。",
        "训练日。",
    ),
}

converted = 0
for record in tracker.get("diet_records", []):
    record_date = str(record.get("Date", ""))[:10]
    if record_date not in diet_translations:
        continue
    food_summary, notes = diet_translations[record_date]
    if record.get("Food Summary") != food_summary:
        if record.get("Food Summary") and not record.get("Food Summary Original"):
            record["Food Summary Original"] = record.get("Food Summary")
        record["Food Summary"] = food_summary
        converted += 1
    if record.get("Notes") != notes:
        if record.get("Notes") and not record.get("Notes Original"):
            record["Notes Original"] = record.get("Notes")
        record["Notes"] = notes

by_id = {
    movement["movement_id"]: movement
    for movement in movement_dictionary.get("movements", [])
    if movement.get("movement_id")
}

history_by_day = {}
for movement in tracker.get("movements", {}).values():
    for history in movement.get("history") or []:
        day = history.get("training_day")
        if day in (None, ""):
            continue
        history_by_day.setdefault(int(day), []).append((movement, history))

for session in tracker.get("training_sessions", []):
    day = session.get("No.")
    try:
        day = int(day)
    except Exception:
        continue
    records = sorted(history_by_day.get(day, []), key=lambda item: int(item[1].get("order") or 0))
    if records:
        session["Standardized Summary"] = "；".join(
            f"第{history.get('order')}个动作：{by_id.get(history.get('movement_id') or movement.get('movement_id'), {}).get('display_name') or movement.get('name', '')}"
            for movement, history in records
        )
    notes = str(session.get("Notes") or "")
    if notes.startswith("New movements:"):
        if not session.get("System Notes Original"):
            session["System Notes Original"] = notes
        session["Notes"] = ""

write(DICT, movement_dictionary)
write(DATA, tracker)
print(f"converted_diet_records={converted}")
