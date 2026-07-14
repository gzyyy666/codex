from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.analysis_export import build_export, render_markdown
from fitness_ledger_core.shared_view_models import LedgerViewModels


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def main() -> None:
    formal = [ROOT / "data" / "tracker.json", ROOT / "data" / "movement_dictionary.json"]
    before = [digest(path) for path in formal]
    start = date(2026, 6, 1)
    body, diet, training, pull_history, press_history = [], [], [], [], []
    for offset in range(30):
        day = (start + timedelta(days=offset)).isoformat()
        body.append({"Date": day, "Weight (kg)": 70 - offset * 0.1 if offset not in {3, 17} else "bad", "Bowel Movement": ["有", "否", "正常", "少量", "", "未知值"][offset % 6], "Training": "上肢" if offset in {0, 7, 14, 21} else "", "Cardio": "跑步机爬坡 30 分钟" if offset == 2 else "", "Notes": "共同备注" if offset == 0 else "身体备注" if offset == 1 else ""})
        diet.append({"Date": day, "Calories (kcal)": 1500 + offset, "Protein (g)": 120, "Carbs (g)": 130 if offset != 5 else "", "Fat (g)": 45, "Food Summary": "早餐 鸡胸肉 200g 练前 香蕉", "Notes": "共同备注" if offset == 0 else "饮食备注" if offset == 1 else ""})
    training.append({"Date": "2026-06-01", "Split": "推", "Raw Record": "不得导出", "Notes": "共同备注"})
    for offset in (0, 7, 14, 21):
        day = (start + timedelta(days=offset)).isoformat()
        pull_history.append({"date": day, "order": 1, "sets": [{"weight": 0, "reps": 10, "sets": 2}], "notes": "最后一组接近力竭", "raw": "hidden"})
        press_history.append({"date": day, "order": 2, "sets": [{"weight": 20 + offset, "reps": 8, "sets": 3}], "notes": "稳定完成"})
    tracker = {"daily_records": body, "diet_records": diet, "training_sessions": training, "movements": {"pull": {"movement_id": "pull", "history": pull_history}, "press": {"movement_id": "press", "history": press_history}}, "raw_entries": [{"date": "2026-06-01", "text": "raw_entries secret"}]}
    dictionary = {"movements": [{"movement_id": "pull", "display_name": "引体向上"}, {"movement_id": "press", "display_name": "卧推"}]}
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-analysis-") as directory:
        directory = Path(directory)
        tracker_file, dictionary_file = directory / "tracker.json", directory / "movement_dictionary.json"
        tracker_file.write_text(json.dumps(tracker, ensure_ascii=False), encoding="utf-8")
        dictionary_file.write_text(json.dumps(dictionary, ensure_ascii=False), encoding="utf-8")
        result = build_export(LedgerViewModels(tracker_file, dictionary_file), {"start": "2026-06-01", "end": "2026-06-30", "include_raw_preview": True})
        markdown = result["markdown"]
        assert set(result) == {"payload", "markdown", "json"}
        assert "- 力量训练次数：4" in markdown and "- 休息日：26" in markdown
        assert "- 记录天数：30" in markdown and "- 动作记录数：8" in markdown
        assert "首末7日均值变化：-2.30 kg" in markdown
        assert "鸡胸肉 200g" not in markdown and "Food Summary" not in markdown and "raw_entries" not in markdown and "不得导出" not in markdown
        assert "calories: 1500" in markdown and "共同备注" in markdown and markdown.count("共同备注") == 1
        assert "- 身体：身体备注" in markdown and "- 饮食：饮食备注" in markdown
        assert "跑步机爬坡 30 分钟" in markdown and "自重 × 10 × 2" in markdown
        assert "最大重量：自重" in markdown and "最大重量：41" in markdown
        assert "未归类：5天" in markdown and "未记录天数：5" in markdown
        assert "#### 2026-06-22" in markdown and "当日动作顺序：第1个动作" in markdown
        short = render_markdown({"range": {"start": "2026-06-01", "end": "2026-06-03"}, "body": [{"Date": "2026-06-01", "Bowel Movement": ""}], "diet": [], "training": [], "movements": [], "raw_entries": []})
        assert "- 休息日：3" in short and "窗口重叠，不作阶段比较" in short and "暂无有效记录" in short
        unordered = render_markdown({"range": {"start": "2026-06-01", "end": "2026-06-14"}, "body": [], "diet": [], "training": [], "movements": [{"movement_id": "x", "display_name": "测试", "history": [{"date": "2026-06-01", "sets": [{"weight_text": "辅助", "reps": 8, "sets": 1}]}, {"date": "2026-06-14", "sets": [{"weight_text": "辅助", "reps": 8, "sets": 1}]}]}], "raw_entries": []})
        assert "当日动作顺序：未记录" in unordered and "最大重量：不适合统一比较" in unordered
        (directory / "fixture.md").write_text(markdown, encoding="utf-8")
    assert before == [digest(path) for path in formal]
    print("ANALYSIS_EXPORT_TEST_OK")


if __name__ == "__main__":
    main()
