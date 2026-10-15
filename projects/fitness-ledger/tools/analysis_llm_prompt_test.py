"""Anonymous contract checks for the external LLM initialization handoff."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.analysis_llm_prompt import (  # noqa: E402
    all_data_example, build_initialization_prompt, request_capabilities,
)
from fitness_ledger_core.analysis_export_request import DATASET_FIELDS, validate_request  # noqa: E402
from web_desktop.backend.analysis_export_protocol import AnalysisExportProtocolService, AnonymousFixtureProvider  # noqa: E402


def test_all_data_round_trip() -> None:
    request = all_data_example()
    assert validate_request(request).valid
    protocol = AnalysisExportProtocolService(AnonymousFixtureProvider(
        ROOT / 'tools/fixtures/analysis_export_anonymous/fixture.json'))
    preview = protocol.preview({'request': request})
    assert preview['status'] == 'preview_ready', preview
    exported = protocol.export({'request': request, 'confirmed': True,
                                'confirmation_token': preview['confirmation_token']})
    assert exported['status'] == 'bundle_ready', exported
    assert exported['safety_flags'] == {
        'raw_included': False, 'executor_called': False, 'formal_data_written': False}
    for format_name in request['output']['formats']:
        artifact = protocol.artifact(exported['artifact_id'], format_name)
        assert artifact and artifact[1]


def test_capabilities_cover_runtime_contract() -> None:
    capabilities = request_capabilities()
    for kind, fields in DATASET_FIELDS.items():
        assert capabilities['datasets'][kind]['fields'] == list(fields)
        for mode in capabilities['datasets'][kind]['time_modes']:
            assert mode in capabilities['time_range_shapes']
    for mode in ('days_before_target_session', 'target_session_day', 'days_after_target_session'):
        req = copy.deepcopy(all_data_example())
        req['datasets'] = [req['datasets'][2], req['datasets'][1]]
        relative = {'mode': mode, 'target_dataset_id': 'training', 'match_mode': 'each_matching_session'}
        if mode != 'target_session_day':
            relative['days_before' if mode.startswith('days_before') else 'days_after'] = 3
            relative['include_target_session_day'] = False
        req['datasets'][1]['time_range'] = relative
        assert validate_request(req).valid


def test_prompt_boundaries() -> None:
    prompt = build_initialization_prompt(themes=[], categories=[], modules=[], library_shape={})
    assert 'filters 必填' in prompt
    assert '自定义 Data Module' in prompt
    assert '初始化后只回复' in prompt
    assert '只有收到真实导出数据包后' in prompt
    assert '不能编造 ID' in prompt
    assert '不得把关系条件简化' in prompt
    assert 'notes_scope' in prompt
    assert 'calories_kcal、protein_g、carbs_g、fat_g' in prompt
    assert 'notes 不是任何类型的合法 fields 项' in prompt
    assert '先说明无法完整满足' in prompt
    assert '需要两阶段' in prompt
    assert '不能把多个请求塞进非法顶层包装' in prompt


def test_failed_comparison_request_is_not_silently_accepted() -> None:
    request = all_data_example()
    diet = copy.deepcopy(request['datasets'][1])
    diet.pop('filters')
    diet['fields'] = ['date', 'calories', 'protein', 'carbs', 'fat', 'food_summary', 'notes']
    body = copy.deepcopy(request['datasets'][0])
    body.pop('filters')
    body['fields'] = ['date', 'weight', 'body_fat', 'muscle_mass', 'sleep', 'notes']
    request['datasets'] = [diet, body]
    result = validate_request(request)
    assert not result.valid
    missing = {error.path for error in result.errors if error.code == 'MISSING_REQUIRED_PROPERTY'}
    assert missing == {'datasets[0].filters', 'datasets[1].filters'}
    unknown = {error.message.split()[1] for error in result.errors if error.code == 'UNKNOWN_FIELD'}
    assert unknown == {'calories', 'protein', 'carbs', 'fat', 'notes', 'weight', 'body_fat', 'muscle_mass', 'sleep'}
    protocol = AnalysisExportProtocolService(AnonymousFixtureProvider(
        ROOT / 'tools/fixtures/analysis_export_anonymous/fixture.json'))
    assert protocol.preview({'request': request})['status'] == 'invalid_request'


if __name__ == '__main__':
    for test in (test_all_data_round_trip, test_capabilities_cover_runtime_contract, test_prompt_boundaries,
                 test_failed_comparison_request_is_not_silently_accepted):
        test()
        print(f'PASS {test.__name__}')
