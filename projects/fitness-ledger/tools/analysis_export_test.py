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
        activity = render_markdown({"range": {"start": "2026-06-01", "end": "2026-06-08"}, "body": [{"Date": "2026-06-01", "Training": "休息"}, {"Date": "2026-06-02", "Training": "肩胸背综合"}, {"Date": "2026-06-03", "Training": "步行 / 无力量训练"}, {"Date": "2026-06-04", "Training": "无力量训练"}, {"Date": "2026-06-05", "Training": ""}, {"Date": "2026-06-06", "Cardio": "步行"}, {"Date": "2026-06-07", "Training": "步行 / 无力量训练"}], "diet": [], "training": [], "movements": [{"movement_id": "x", "display_name": "测试", "history": [{"date": "2026-06-01", "sets": []}, {"date": "2026-06-07", "sets": []}]}], "raw_entries": []})
        assert "- 力量训练次数：3" in activity and "- 休息日：5" in activity
        bowel = render_markdown({"range": {"start": "2026-06-01", "end": "2026-06-10"}, "body": [{"Date": f"2026-06-{day:02d}", "Bowel Movement": value} for day, value in enumerate(["有", "是", "正常", "少量", "称重后有", "是。称重后，少量", "称重后少量", "无", "否", ""], 1)], "diet": [], "training": [], "movements": [], "raw_entries": []})
        assert "- 排便天数：7" in bowel and "- 未排便天数：2" in bowel and "- 未记录天数：1" in bowel and "未归类" not in bowel
        unknown_bowel = render_markdown({"range": {"start": "2026-06-01", "end": "2026-06-02"}, "body": [{"Date": "2026-06-01", "Bowel Movement": "没有"}, {"Date": "2026-06-02", "Bowel Movement": "未知"}], "diet": [], "training": [], "movements": [], "raw_entries": []})
        assert "- 未归类：2天" in unknown_bowel
        unordered = render_markdown({"range": {"start": "2026-06-01", "end": "2026-06-14"}, "body": [], "diet": [], "training": [], "movements": [{"movement_id": "x", "display_name": "测试", "history": [{"date": "2026-06-01", "sets": [{"weight_text": "辅助", "reps": 8, "sets": 1}]}, {"date": "2026-06-14", "sets": [{"weight_text": "辅助", "reps": 8, "sets": 1}]}]}], "raw_entries": []})
        assert "当日动作顺序：未记录" in unordered and "最大重量：不适合统一比较" in unordered

        coverage_specs = [
            ("chest", "胸部代表", "Chest", 2), ("back", "背部代表", "Back", 7),
            ("shoulder", "肩部代表", "Shoulder", 8), ("arms", "手臂代表", "Arms", 3),
            ("legs", "腿部代表", "Legs", 2), ("core", "核心代表", "Core", 2),
            *[(f"extra-{index}", f"补充{index:02d}", "Shoulder", 2) for index in range(12)],
        ]
        coverage_movements = []
        for movement_id, name, muscle_group, count in coverage_specs:
            coverage_movements.append({
                "movement_id": movement_id,
                "display_name": name,
                "muscle_group": muscle_group,
                "history": [{"date": f"2026-06-{day:02d}", "order": 1, "sets": [{"weight": 10, "reps": 10, "sets": 1}]} for day in range(1, count + 1)],
            })
        coverage = render_markdown({"range": {"start": "2026-06-01", "end": "2026-06-30"}, "body": [], "diet": [], "training": [], "movements": coverage_movements, "raw_entries": []})
        trend = coverage.split("# 高频动作趋势", 1)[1].split("# 导出说明", 1)[0]
        trend_names = [line[3:] for line in trend.splitlines() if line.startswith("## ") and line != "## 统计规则"]
        assert len(trend_names) == 16 and len(set(trend_names)) == 16
        assert {"胸部代表", "背部代表", "肩部代表", "手臂代表", "腿部代表", "核心代表"}.issubset(trend_names)
        assert trend_names[:3] == ["肩部代表", "背部代表", "手臂代表"]
        assert "最多展示16个动作" in trend

        notes_payload = {"range": {"start": "2026-06-01", "end": "2026-06-14"}, "body": [{"Date": "2026-06-01", "Notes": "晚间称重，与次日晨间数据不可直接比较。高碳导致糖原和水分变化。"}], "diet": [{"Date": "2026-06-01", "Notes": "聚餐，热量只能估算。明日建议回归高蛋白低油饮食。"}], "training": [{"Date": "2026-06-01", "Notes": "卧推：末组接近力竭；整体训练因接听电话质量下降。"}], "movements": [{"movement_id": "press", "display_name": "卧推", "muscle_group": "Chest", "history": [{"date": "2026-06-01", "order": 1, "sets": [{"weight": 60, "reps": 8, "sets": 1}], "notes": "末组接近力竭"}, {"date": "2026-06-14", "order": 1, "sets": [{"weight": 60, "reps": 8, "sets": 1}]}]}], "raw_entries": []}
        notes_before = json.dumps(notes_payload, ensure_ascii=False, sort_keys=True)
        notes_markdown = render_markdown(notes_payload)
        assert "晚间称重，与次日晨间数据不可直接比较。" in notes_markdown
        assert "聚餐，热量只能估算。" in notes_markdown
        assert "整体训练因接听电话质量下降。" in notes_markdown
        assert "高碳导致糖原和水分变化。" not in notes_markdown
        assert "明日建议回归高蛋白低油饮食。" not in notes_markdown
        assert notes_markdown.count("末组接近力竭") == 2
        assert notes_before == json.dumps(notes_payload, ensure_ascii=False, sort_keys=True)

        preserve_parts = [
            "晚间称重，非晨起空腹。", "测量条件不同，存在测量误差。", "身体不适，左肘关节不适。",
            "聚餐后高油高盐，热量估算存在误差。", "临时调整饮食计划。", "天气导致暂停训练。",
            "户外步行约15000步。", "接听电话导致训练质量下降。", "体力异常，持续输出不足。",
            "动作首次尝试，行程缩短。", "目标肌肉感觉更好，后束明显乏力。",
            "核心稳定性波动，本次不作为力量退步判断。", "末组接近力竭，控制完成，个人最佳。",
            "后续安排下次调整训练顺序。",
        ]
        generic_parts = [
            "高碳导致糖原和水分变化。", "高钠导致水分潴留。", "未排便影响次日体重波动。",
            "胃肠内容物导致体重波动。", "单日体重不宜直接解读为脂肪增加。", "蛋白质有利于恢复。",
            "训练日碳水有利于训练输出。", "符合当前减脂目标。", "适合作为高碳训练日。",
            "整体恢复供能充足。", "建议补充蛋白。", "不需要极端断食补偿。",
        ]
        template_notes = render_markdown({"range": {"start": "2026-06-01", "end": "2026-06-02"}, "body": [{"Date": "2026-06-01", "Notes": "".join(preserve_parts + generic_parts)}], "diet": [], "training": [], "movements": [], "raw_entries": []})
        for part in preserve_parts:
            assert part in template_notes
        for part in generic_parts:
            assert part not in template_notes

        fragment_notes = render_markdown({"range": {"start": "2026-06-01", "end": "2026-06-02"}, "body": [{"Date": "2026-06-01", "Notes": "今日为背部高碳日，整体训练容量较高，动作首次尝试，轨迹需要继续观察。饮食结构呈现中高脂特征，脂肪主要来源于聚餐叠加。当前体重较前日下降，更多受水分波动影响，而非真实脂肪变化。"}], "diet": [], "training": [], "movements": [], "raw_entries": []})
        assert "背部高碳日" not in fragment_notes and "整体训练容量较高" not in fragment_notes
        assert "饮食结构呈现" not in fragment_notes and "脂肪主要来源于" not in fragment_notes
        assert "当前体重较前日下降" not in fragment_notes
        assert "动作首次尝试，轨迹需要继续观察。" in fragment_notes
        assert "notes:\n。" not in fragment_notes and "影响，而非真实脂肪变化" not in fragment_notes
        (directory / "fixture.md").write_text(markdown, encoding="utf-8")
    assert before == [digest(path) for path in formal]
    print("ANALYSIS_EXPORT_TEST_OK")


if __name__ == "__main__":
    main()
