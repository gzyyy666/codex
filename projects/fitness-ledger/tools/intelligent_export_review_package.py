"""Create a privacy-safe human review package from structural run results."""
from __future__ import annotations
import argparse, json, tempfile
from datetime import datetime, timezone
from pathlib import Path

PROMPTS = [
    "\u770b\u770b\u6211\u6700\u8fd1\u51cf\u8102\u600e\u4e48\u6837\uff0c\u8bad\u7ec3\u6709\u6ca1\u6709\u53d7\u5f71\u54cd",
    "\u5206\u6790\u6700\u8fd1\u4f4e\u78b3\u662f\u5426\u5bfc\u81f4\u80f8\u90e8\u8bad\u7ec3\u8868\u73b0\u4e0b\u964d",
    "\u5bfc\u51fa\u5173\u4e8e\u5367\u63a8\u6700\u8fd1\u4e00\u6bb5\u65f6\u95f4\u6700\u6709\u4ef7\u503c\u7684\u6570\u636e",
    "\u770b\u770b\u8fd9\u51e0\u4e2a\u6708\u80a9\u90e8\u8bad\u7ec3\u662f\u5426\u6709\u8fdb\u6b65",
]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--results", default=""); ap.add_argument("--output", default=""); args = ap.parse_args()
    results = json.loads(Path(args.results).read_text(encoding="utf-8")) if args.results else {"status": "blocked", "reason": "real Ollama health check unavailable"}
    out = Path(args.output) if args.output else Path(tempfile.gettempdir()) / ("fitness-ledger-intelligent-export-review-" + datetime.now().strftime("%Y%m%d-%H%M%S")); out.mkdir(parents=True, exist_ok=True)
    safe = {"generated_at": datetime.now(timezone.utc).isoformat(), "status": results.get("status"), "reason": results.get("reason", results.get("health", {}).get("code", "")), "privacy": "No tracker, Notes, Raw, formal paths, or full prompts included.", "requests": [{"label": i + 1, "request": p, "status": "not_run"} for i, p in enumerate(PROMPTS)]}
    (out / "review.json").write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Fitness Ledger Intelligent Export Core Review", "", "## 状态", f"- 当前状态：{safe['status']}", f"- 阻断原因：{safe['reason']}", "- 本包仅包含结构性诊断，不包含正式数据、完整 Notes、Raw 或路径。", "", "## 请求清单"]
    for item in safe["requests"]: lines.extend([f"### {item['label']}", f"- 请求：{item['request']}", f"- 状态：{item['status']}"])
    lines.extend(["", "## 人工审阅结论提示", "当前未生成真实模型选择，不能据此判断选少、选多或选错。待 Ollama 健康检查恢复后，重新运行四类请求并生成完整选择 Review。", ""])
    (out / "review.md").write_text("\n".join(lines), encoding="utf-8")
    print(str(out))

if __name__ == "__main__": main()
