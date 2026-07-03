from __future__ import annotations

import json


def render_markdown(payload: dict) -> str:
    summary, period = payload["summary"], payload["range"]
    lines = [
        "# Fitness Ledger Analysis Export",
        "",
        f"- Range: {period['start']} to {period['end']}",
        f"- Logged days: {summary['days']}",
        f"- Training sessions: {summary['training_sessions']}",
        f"- Movement records: {summary['movement_records']}",
        f"- Weight: {summary['weight_start']} -> {summary['weight_end']}",
        "",
        "## Training",
    ]
    for row in payload["training"]:
        lines.append(f"- {row.get('Date', '')}: {row.get('Split', '')} | {row.get('Standardized Summary', '')}")
    lines.extend(["", "## Movement history"])
    for movement in payload["movements"]:
        lines.append(f"### {movement['display_name']} ({movement['muscle_group']})")
        for row in movement["history"]:
            metrics = row["metrics"]
            lines.append(f"- {row.get('date', '')}: max {metrics['max_weight']} kg, reps {metrics['total_reps']}, volume {metrics['volume']}")
    return "\n".join(lines).strip() + "\n"


def build_export(view_models, request: dict) -> dict:
    payload = view_models.analysis(
        start=str(request.get("start", "")),
        end=str(request.get("end", "")),
        days=int(request.get("days", 14)),
        include_raw_preview=bool(request.get("include_raw_preview", False)),
    )
    return {
        "payload": payload,
        "markdown": render_markdown(payload),
        "json": json.dumps(payload, ensure_ascii=False, indent=2),
    }
