from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from local_semantic_request_interpreter_lab.core import DraftError, compile_request_draft, interpret_request, parse_json_strict, validate_request_draft, validate_request_grounding
from local_semantic_request_interpreter_lab.deterministic import parse_chinese_number, parse_deterministic_intent
from local_semantic_request_interpreter_lab.evaluate import run_evaluation
from local_semantic_request_interpreter_lab.inference import EmptyOutputError, InferenceProvider, InvalidModelOutputError, ProcessExitError, ProcessStartError, ProcessTimeoutError, ProviderConfigurationError
from local_semantic_request_interpreter_lab.llama_runner import LlamaCppCliProvider, LlamaJsonRunner
from local_semantic_request_interpreter_lab.runtime_config import ModelProfile, RuntimeConfig, load_runtime_bundle


ROOT = Path(__file__).parents[1]
CATALOG = json.loads((ROOT / "data" / "capability_catalog.json").read_text(encoding="utf-8"))


def good_draft() -> dict:
    return {
        "schema_version": "fitness-ledger-request-draft-v1",
        "status": "ready",
        "purpose": "比较最近三次胸训的训练容量，并结合此前饮食交给 GPT 分析。",
        "datasets": [
            {"draft_id": "target_training", "kind": "training", "scope": {"body_part": "chest"}, "time_intent": {"type": "latest_matching_sessions", "count": 3}, "requested_information": ["session", "movements", "sets"], "notes": {"requested": False, "scopes": []}},
            {"draft_id": "preceding_diet", "kind": "diet", "scope": {}, "time_intent": {"type": "before_each_target_event", "target_draft_id": "target_training", "days_before": 3, "include_target_day": False}, "requested_information": ["energy", "carbohydrate"], "notes": {"requested": False, "scopes": []}},
        ],
        "relations": [{"type": "preceding_event_window", "source_draft_id": "target_training", "dependent_draft_id": "preceding_diet"}],
        "missing_confirmations": [],
        "warnings": [],
    }


class LabTests(unittest.TestCase):
    def _runtime_files(self, root: Path, *, cuda: bool = False) -> tuple[Path, Path]:
        runtime_root = root / "runtime root with spaces"
        bin_dir = runtime_root / ("llama-cuda" if cuda else "llama")
        bin_dir.mkdir(parents=True)
        executable = bin_dir / "llama-cli.exe"
        executable.write_bytes(b"fake")
        if cuda:
            (bin_dir / "ggml-cuda.dll").write_bytes(b"fake")
        (runtime_root / "json_schema_to_grammar.py").write_text("print('root ::= \\\"x\\\"')", encoding="utf-8")
        model = root / "model file with spaces.gguf"
        model.write_bytes(b"fake")
        return executable, model

    def _provider(self, root: Path, *, cuda: bool = False) -> LlamaCppCliProvider:
        executable, model = self._runtime_files(root, cuda=cuda)
        profile = ModelProfile("test-model", model)
        config = RuntimeConfig(executable, backend="cuda" if cuda else "cpu", gpu_layers=99 if cuda else 0, timeout_seconds=3)
        return LlamaCppCliProvider(profile, config, ROOT / "schema" / "request_draft_v1.schema.json")

    def test_valid_draft_and_compile_is_read_only(self):
        draft = validate_request_draft(good_draft(), CATALOG)
        compiled = compile_request_draft(draft, CATALOG)
        self.assertFalse(compiled["execution"]["allowed"])
        self.assertFalse(compiled["execution"]["executor_called"])
        self.assertFalse(compiled["execution"]["write_allowed"])
        self.assertFalse(compiled["execution"]["raw"])

    def test_unknown_field_fails_closed(self):
        draft = good_draft()
        draft["datasets"][0]["unknown"] = True
        with self.assertRaises(DraftError):
            validate_request_draft(draft, CATALOG)

    def test_raw_and_duplicate_json_fail_closed(self):
        draft = good_draft()
        draft["raw"] = True
        with self.assertRaises(DraftError):
            validate_request_draft(draft, CATALOG)
        with self.assertRaises(DraftError):
            parse_json_strict('{"a": 1, "a": 2}')

    def test_model_unavailable_fails_closed(self):
        result = interpret_request("导出最近饮食", CATALOG)
        self.assertEqual(result["status"], "model_unavailable")
        self.assertIsNone(result["draft"])

    def test_before_window_requires_relation(self):
        draft = good_draft()
        draft["relations"] = []
        with self.assertRaises(DraftError):
            validate_request_draft(draft, CATALOG)

    def test_grounding_rejects_expanded_scope(self):
        draft = good_draft()
        draft["datasets"][0]["scope"]["movement"] = "bench_press"
        draft["datasets"][0]["scope"]["split"] = "push"
        draft["datasets"][0]["time_intent"] = {"type": "recent_days", "days": 90}
        with self.assertRaises(DraftError):
            validate_request_grounding(draft, "最近三次胸训和每次训练前三天的饮食，给 GPT 分析训练容量变化。")

    def test_chinese_and_arabic_number_canonicalization(self):
        self.assertEqual(parse_chinese_number("一"), 1)
        self.assertEqual(parse_chinese_number("两"), 2)
        self.assertEqual(parse_chinese_number("三"), 3)
        self.assertEqual(parse_chinese_number("十四"), 14)
        self.assertEqual(parse_chinese_number("28"), 28)

    def test_deterministic_ready_gold_subset_is_exact(self):
        cases = json.loads((ROOT / "data" / "gold_cases.json").read_text(encoding="utf-8"))
        for case in cases[:19]:
            with self.subTest(case_id=case["case_id"]):
                intent = parse_deterministic_intent(case["text"], CATALOG)
                self.assertEqual(intent.route, "deterministic")
                draft = validate_request_draft(intent.to_draft(), CATALOG)
                validate_request_grounding(draft, case["text"])
                self.assertEqual(draft["status"], case["status"])
                self.assertEqual([item["kind"] for item in draft["datasets"]], [item["kind"] for item in case["datasets"]])
                for expected in case["datasets"]:
                    actual = next(item for item in draft["datasets"] if item["draft_id"] == expected["draft_id"])
                    for field in ("scope", "time_intent", "requested_information", "notes"):
                        self.assertEqual(actual[field], expected[field], field)
                self.assertEqual(draft["relations"], case["relations"])

    def test_deterministic_unsupported_and_confirmation_routes(self):
        cases = json.loads((ROOT / "data" / "gold_cases.json").read_text(encoding="utf-8"))
        for case in cases[20:]:
            with self.subTest(case_id=case["case_id"]):
                intent = parse_deterministic_intent(case["text"], CATALOG)
                self.assertEqual(intent.route, "deterministic")
                self.assertEqual(intent.status, case["status"])
                if case["status"] == "needs_confirmation":
                    self.assertTrue(intent.missing_confirmations)

    def test_deterministic_success_skips_provider(self):
        class MustNotRun(InferenceProvider):
            def infer(self, user_text: str) -> str:
                raise AssertionError("deterministic request called provider")

        result = interpret_request("导出最近三次胸训的训练、动作和组数。", CATALOG, MustNotRun())
        self.assertEqual(result["status"], "ready")

    def test_incomplete_intent_does_not_guess(self):
        class MustNotRun(InferenceProvider):
            def infer(self, user_text: str) -> str:
                raise AssertionError("incomplete request called provider")

        result = interpret_request("导出最近几次训练，但我没说要哪几次。", CATALOG, MustNotRun())
        self.assertEqual(result["status"], "needs_confirmation")
        self.assertEqual(result["draft"]["status"], "needs_confirmation")

    def test_semantic_hint_case_is_the_only_gold_provider_route(self):
        cases = json.loads((ROOT / "data" / "gold_cases.json").read_text(encoding="utf-8"))
        routes = {case["case_id"]: parse_deterministic_intent(case["text"], CATALOG).route for case in cases}
        self.assertEqual(sum(route == "deterministic" for route in routes.values()), 29)
        self.assertEqual(sum(route == "provider" for route in routes.values()), 1)

    def test_inference_provider_contract_and_core_failure_close(self):
        class StubProvider(InferenceProvider):
            def __init__(self):
                self.calls = 0

            def infer(self, user_text: str) -> str:
                self.calls += 1
                return json.dumps({
                    "schema_version": "fitness-ledger-request-draft-v1",
                    "status": "unsupported",
                    "purpose": "test",
                    "datasets": [],
                    "relations": [],
                    "missing_confirmations": [],
                    "warnings": [],
                })

        provider = StubProvider()
        result = interpret_request("导出最近饮食", CATALOG, provider)
        self.assertEqual(result["status"], "unsupported")
        self.assertEqual(provider.calls, 1)

        class FailedProvider(InferenceProvider):
            def infer(self, user_text: str) -> str:
                raise ProcessTimeoutError("3s")

        failed = interpret_request("导出最近饮食", CATALOG, FailedProvider())
        self.assertEqual(failed["status"], "model_unavailable")
        self.assertIsNone(failed["draft"])

        class InvalidProvider(InferenceProvider):
            def infer(self, user_text: str) -> str:
                return "not json"

        invalid = interpret_request("导出最近饮食", CATALOG, InvalidProvider())
        self.assertEqual(invalid["status"], "invalid_model_output")
        self.assertIsNone(invalid["draft"])

    def test_runtime_config_validation_and_cpu_cuda_layers(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            executable, model = self._runtime_files(root)
            with self.assertRaises(ProviderConfigurationError):
                RuntimeConfig(executable, backend="cpu", gpu_layers=1)
            with self.assertRaises(ProviderConfigurationError):
                RuntimeConfig(executable, backend="cuda", gpu_layers=99)
            with self.assertRaises(ProviderConfigurationError):
                ModelProfile("missing", root / "missing.gguf")
            with self.assertRaises(ProviderConfigurationError):
                RuntimeConfig(root / "missing.exe")
            with self.assertRaises(ProviderConfigurationError):
                RuntimeConfig(executable, timeout_seconds=0)
            bundle = load_runtime_bundle(model_path=model, executable_path=executable, timeout_seconds=12)
            self.assertEqual(bundle.runtime_config.backend, "cpu")
            self.assertEqual(bundle.runtime_config.timeout_seconds, 12)
            self.assertIsInstance(LlamaJsonRunner(executable, model, ROOT / "schema" / "request_draft_v1.schema.json"), InferenceProvider)

    def test_runtime_json_priority_and_windows_command_paths(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            executable, model = self._runtime_files(root)
            config_path = root / "runtime config.json"
            config_path.write_text(json.dumps({
                "model_profile": {"name": "config-model", "model_path": str(root / "missing from config.gguf"), "format": "gguf"},
                "runtime_config": {"executable_path": str(executable), "backend": "cpu", "gpu_layers": 0, "timeout_seconds": 12},
            }), encoding="utf-8")
            override_model = root / "override.gguf"
            override_model.write_bytes(b"fake")
            bundle = load_runtime_bundle(config_path, model_path=override_model, timeout_seconds=33)
            self.assertEqual(bundle.model_profile.model_path, override_model)
            self.assertEqual(bundle.runtime_config.timeout_seconds, 33)
            provider = LlamaCppCliProvider(bundle.model_profile, bundle.runtime_config, ROOT / "schema" / "request_draft_v1.schema.json")
            command = provider.build_command("prompt with spaces", root / "grammar file.gbnf")
            self.assertEqual(command[0], str(executable))
            self.assertIn(str(override_model), command)
            self.assertIn("prompt with spaces", command)
            self.assertNotIn("--n-gpu-layers", command)

    def test_cuda_command_contains_gpu_layers(self):
        with tempfile.TemporaryDirectory() as raw:
            provider = self._provider(Path(raw), cuda=True)
            command = provider.build_command("prompt", Path(raw) / "grammar.gbnf")
            self.assertIn("--n-gpu-layers", command)
            self.assertEqual(command[command.index("--n-gpu-layers") + 1], "99")

    @mock.patch("local_semantic_request_interpreter_lab.llama_runner.subprocess.check_output", return_value='root ::= "x"')
    def test_provider_success_result(self, _grammar):
        with tempfile.TemporaryDirectory() as raw:
            provider = self._provider(Path(raw))
            completed = subprocess.CompletedProcess([], 0, stdout='banner\n{"status":"ready"}\n', stderr="")
            with mock.patch("local_semantic_request_interpreter_lab.llama_runner.subprocess.run", return_value=completed):
                self.assertEqual(provider.infer("test"), '{"status":"ready"}')

    def test_provider_process_failure_categories(self):
        scenarios = [
            (OSError("missing"), ProcessStartError),
            (subprocess.TimeoutExpired(["llama-cli"], 1), ProcessTimeoutError),
            (None, ProcessExitError),
            (None, EmptyOutputError),
            (None, InvalidModelOutputError),
        ]
        for side_effect, expected in scenarios:
            with self.subTest(expected=expected.__name__), tempfile.TemporaryDirectory() as raw:
                provider = self._provider(Path(raw))
                if expected is ProcessExitError:
                    value = subprocess.CompletedProcess([], 7, stdout="", stderr="error")
                    patcher = mock.patch("local_semantic_request_interpreter_lab.llama_runner.subprocess.run", return_value=value)
                elif expected is EmptyOutputError:
                    value = subprocess.CompletedProcess([], 0, stdout="", stderr="")
                    patcher = mock.patch("local_semantic_request_interpreter_lab.llama_runner.subprocess.run", return_value=value)
                elif expected is InvalidModelOutputError:
                    value = subprocess.CompletedProcess([], 0, stdout="no json", stderr="")
                    patcher = mock.patch("local_semantic_request_interpreter_lab.llama_runner.subprocess.run", return_value=value)
                else:
                    patcher = mock.patch("local_semantic_request_interpreter_lab.llama_runner.subprocess.run", side_effect=side_effect)
                with patcher, mock.patch("local_semantic_request_interpreter_lab.llama_runner.subprocess.check_output", return_value='root ::= "x"'):
                    with self.assertRaises(expected):
                        provider.infer("test")

    def test_evaluator_accepts_provider_contract(self):
        class UnsupportedProvider(InferenceProvider):
            def infer(self, user_text: str) -> str:
                return json.dumps({
                    "schema_version": "fitness-ledger-request-draft-v1",
                    "status": "unsupported",
                    "purpose": "test",
                    "datasets": [],
                    "relations": [],
                    "missing_confirmations": [],
                    "warnings": [],
                })

        case = {"case_id": "T1", "text": "导出最近饮食", "status": "unsupported", "datasets": []}
        report = run_evaluation(UnsupportedProvider(), CATALOG, [case])
        self.assertEqual(report["cases"], 1)
        self.assertEqual(report["metrics"]["status"], 1.0)


if __name__ == "__main__":
    unittest.main()
