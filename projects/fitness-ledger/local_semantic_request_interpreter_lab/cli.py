"""Command-line demo for the narrow interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import compile_request_draft, interpret_request
from .llama_runner import LlamaJsonRunner


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Fitness Ledger Local Semantic Request Interpreter Lab")
    parser.add_argument("text", nargs="?", default="最近三次胸训和每次训练前三天的饮食，给 GPT 分析训练容量变化。")
    parser.add_argument("--model", required=True)
    parser.add_argument("--llama-cli", required=True)
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()
    root = Path(__file__).parent
    catalog = json.loads((root / "data" / "capability_catalog.json").read_text(encoding="utf-8"))
    schema = root / "schema" / "request_draft_v1.schema.json"
    result = interpret_request(args.text, catalog, LlamaJsonRunner(args.llama_cli, args.model, schema, args.timeout))
    if result.get("status") == "ready":
        result["compiled"] = compile_request_draft(result["draft"], catalog)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"ready", "needs_confirmation", "unsupported"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
