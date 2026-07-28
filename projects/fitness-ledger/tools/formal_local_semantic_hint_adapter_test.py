"""Contract, routing, provider, and stop-before-Web integration tests."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.formal_analysis_request_adapter import FormalAnalysisRequestAdapter
from fitness_ledger_core.formal_analysis_request_preview_service import FormalAnalysisRequestPreviewService
from fitness_ledger_core.formal_local_semantic_hint import (
    SemanticHintError,
    SemanticHintRequest,
    parse_json_strict,
    validate_semantic_hint,
)
from fitness_ledger_core.formal_local_semantic_provider import (
    InferenceProvider,
    LlamaCppCliSemanticHintProvider,
    ModelProfile,
    ProviderConfigurationError,
    ProviderTimeoutError,
    RuntimeBundle,
    RuntimeConfig,
)


class FakeProvider(InferenceProvider):
    def __init__(self, output: dict | Exception) -> None:
        self.output = output
        self.calls = 0

    def infer_semantic_hint(self, request: SemanticHintRequest) -> str:
        self.calls += 1
        if isinstance(self.output, Exception):
            raise self.output
        return json.dumps(self.output, ensure_ascii=False)


def valid_hint() -> dict:
    return {
        "candidates": [
            {
                "dimension": "requested_information",
                "canonical_value": "cross_dataset_analysis",
                "evidence": "分析",
                "confidence": 0.99,
            },
        ],
        "ambiguities": [],
    }


def test_deterministic_preview_contract() -> None:
    provider = FakeProvider(valid_hint())
    adapter = FormalAnalysisRequestAdapter(provider)
    response = adapter.preview("导出最近四周体重和蛋白")
    assert response["status"] == "ready", response
    assert response["route"] == "deterministic"
    assert response["provider_called"] is False
    assert provider.calls == 0
    assert response["request"]["raw"] is False
    assert [item["type"] for item in response["request"]["datasets"]] == ["body", "diet"]
    assert response["execution"] == {
        "allowed": False,
        "executor_called": False,
        "formal_data_written": False,
        "raw_allowed": False,
    }


def test_time_relation_notes_and_movement() -> None:
    adapter = FormalAnalysisRequestAdapter()
    relation = adapter.preview("导出最近三次训练和每次训练前三天的饮食")
    assert relation["status"] == "ready", relation
    datasets = {item["type"]: item for item in relation["request"]["datasets"]}
    assert datasets["training"]["time_range"] == {
        "mode": "latest_matching_sessions",
        "sessions": 3,
    }
    assert datasets["diet"]["time_range"] == {
        "mode": "days_before_target_session",
        "days_before": 3,
        "target_dataset_id": datasets["training"]["dataset_id"],
        "match_mode": "each_matching_session",
        "include_target_session_day": False,
    }
    notes = adapter.preview("导出最近28天饮食热量和饮食笔记")
    assert notes["status"] == "ready", notes
    assert notes["request"]["datasets"][0]["notes_scope"] == "diet"
    movement = adapter.preview("导出最近三次杠铃卧推的负重和组数")
    assert movement["status"] == "ready", movement
    selector = movement["request"]["datasets"][0]["filters"]["movement_selector"]
    assert selector == {"kind": "movement_name", "value": "杠铃卧推"}


def test_confirmation_planner_and_capability_boundaries() -> None:
    adapter = FormalAnalysisRequestAdapter()
    assert adapter.preview("导出体重")["status"] == "needs_confirmation"
    assert adapter.preview("导出最近7天饮食笔记和训练备注")["status"] == "ready"
    assert adapter.preview("分析饮食是否影响训练")["status"] == "planner_required"
    for text in (
        "导出最近7天原始数据",
        "删除最近7天训练",
        "制定训练计划",
    ):
        response = adapter.preview(text)
        assert response["status"] == "unsupported", (text, response)
        assert response["provider_called"] is False
        assert response["request"] is None


def test_grounded_hint_path_and_fail_closed() -> None:
    provider = FakeProvider(valid_hint())
    response = FormalAnalysisRequestAdapter(provider).preview("分析最近一个月训练和饮食")
    assert provider.calls == 1
    assert response["status"] == "ready", response
    assert response["route"] == "semantic_hint"
    assert response["provider_called"] is True
    assert response["request"]["raw"] is False
    assert [item["type"] for item in response["request"]["datasets"]] == ["diet", "training"]
    assert response["semantic_hint"]["candidates"][0]["canonical_value"] == "cross_dataset_analysis"

    invalids = []
    protected = valid_hint()
    protected["candidates"][0]["dimension"] = "time_range"
    invalids.append(protected)
    outside = valid_hint()
    outside["candidates"][0]["canonical_value"] = "raw"
    invalids.append(outside)
    ungrounded = valid_hint()
    ungrounded["candidates"][0]["evidence"] = "未出现"
    invalids.append(ungrounded)
    for value in invalids:
        response = FormalAnalysisRequestAdapter(FakeProvider(value)).preview("分析最近一个月训练和饮食")
        assert response["status"] == "invalid_model_output", response
        assert response["request"] is None
        assert response["execution"]["executor_called"] is False


def test_hint_validator_contract() -> None:
    request = SemanticHintRequest(
        "比较训练",
        {"fields.training": ("split", "standardized_summary")},
        {"fields.training": ("训练",)},
        ("fields.training",),
    )
    value = {
        "candidates": [{
            "dimension": "fields.training",
            "canonical_value": "split",
            "evidence": "训练",
            "confidence": 0.8,
        }],
        "ambiguities": [],
    }
    assert validate_semantic_hint(value, request).candidates[0].canonical_value == "split"
    try:
        parse_json_strict('{"candidates":[],"candidates":[],"ambiguities":[]}')
    except SemanticHintError as exc:
        assert "DUPLICATE_FIELD" in str(exc)
    else:
        raise AssertionError("duplicate JSON field was accepted")


def _bundle(root: Path, *, backend: str = "cuda", gpu_layers: int = 99) -> RuntimeBundle:
    executable = root / "runtime with spaces" / "llama cli.exe"
    model = root / "models with spaces" / "model.gguf"
    grammar = root / "grammar tool.py"
    prompt = root / "prompt.txt"
    for path in (executable, model, grammar, prompt):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
    return RuntimeBundle(
        ModelProfile("test", model),
        RuntimeConfig(
            executable_path=executable,
            grammar_tool_path=grammar,
            runtime_directory=root / "temp files",
            backend=backend,
            gpu_layers=gpu_layers,
            timeout_seconds=2,
        ),
    )


def test_runtime_contract_and_windows_argv() -> None:
    with tempfile.TemporaryDirectory() as name:
        root = Path(name)
        bundle = _bundle(root)
        provider = LlamaCppCliSemanticHintProvider(bundle, root / "prompt.txt")
        command = provider.build_command("含 空格", root / "grammar file.gbnf")
        assert command[0] == str(bundle.runtime_config.executable_path)
        assert str(bundle.model_profile.model_path) in command
        assert "含 空格" in command
        assert command[command.index("--n-gpu-layers") + 1] == "99"
        try:
            _bundle(root, backend="cpu", gpu_layers=1).validate()
        except ProviderConfigurationError as exc:
            assert str(exc) == "CPU_GPU_LAYERS_CONFLICT"
        else:
            raise AssertionError("inconsistent CPU configuration was accepted")


def test_provider_success_timeout_and_cleanup() -> None:
    request = SemanticHintRequest(
        "比较训练",
        {"fields.training": ("split",)},
        {"fields.training": ("训练",)},
        ("fields.training",),
    )
    with tempfile.TemporaryDirectory() as name:
        root = Path(name)
        provider = LlamaCppCliSemanticHintProvider(_bundle(root), root / "prompt.txt")
        completed = subprocess.CompletedProcess([], 0, stdout='noise {"candidates":[],"ambiguities":[]} tail', stderr="")
        with patch("fitness_ledger_core.formal_local_semantic_provider.subprocess.check_output", return_value="root ::= object"), patch(
            "fitness_ledger_core.formal_local_semantic_provider.subprocess.run",
            return_value=completed,
        ):
            assert provider.infer_semantic_hint(request) == '{"candidates":[],"ambiguities":[]}'
        assert not list((root / "temp files").glob("formal-semantic-hint-*"))
        with patch("fitness_ledger_core.formal_local_semantic_provider.subprocess.check_output", return_value="root ::= object"), patch(
            "fitness_ledger_core.formal_local_semantic_provider.subprocess.run",
            side_effect=subprocess.TimeoutExpired("llama", 2),
        ):
            try:
                provider.infer_semantic_hint(request)
            except ProviderTimeoutError:
                pass
            else:
                raise AssertionError("provider timeout did not fail closed")
        assert not list((root / "temp files").glob("formal-semantic-hint-*"))


def test_preview_service_bad_config_and_web_boundary() -> None:
    service = FormalAnalysisRequestPreviewService.from_runtime_config("missing-config.json")
    deterministic = service.preview("导出最近7天体重")
    assert deterministic["status"] == "ready"
    hinted = service.preview("分析最近一个月训练和饮食")
    assert hinted["status"] == "needs_confirmation"
    assert hinted["request"] is None
    assert service.provider_configuration_error == "ProviderConfigurationError"

    web_files = [
        ROOT / "web" / "backend" / "server.py",
        ROOT / "web" / "frontend" / "app.js",
    ]
    for path in web_files:
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert "FormalAnalysisRequestPreviewService" not in text
            assert "formal-local-semantic-hint" not in text


def main() -> None:
    tests = [
        value for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
    print(f"formal local SemanticHint adapter tests passed: {len(tests)}")


if __name__ == "__main__":
    main()
