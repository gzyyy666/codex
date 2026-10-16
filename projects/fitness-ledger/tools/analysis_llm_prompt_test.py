"""Anonymous contract checks for the external LLM initialization handoff."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
from unittest.mock import patch

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


def test_capability_snapshot_tracks_current_contract() -> None:
    original = request_capabilities()
    assert len(original['contract_fingerprint']) == 64
    assert original == request_capabilities()
    # A new supported field must appear in the generated prompt contract,
    # without relying on a hand-maintained example or historical field list.
    with patch.dict(DATASET_FIELDS, {'body': (*DATASET_FIELDS['body'], 'future_metric')}):
        changed = request_capabilities()
        assert 'future_metric' in changed['datasets']['body']['fields']
        assert changed['contract_fingerprint'] != original['contract_fingerprint']
    assert request_capabilities() == original


def test_real_complex_request_and_serialization_guards() -> None:
    purpose = '评估2026年10月8日起增肌阶段的饮食、体重与训练表现。提取10月1日至16日体重及10月8日至16日饮食，判断热量维持或轻微盈余的可能性。重点比较增肌期与此前可比训练阶段的表现：先提取9月1日至29日的历史训练组织及单次训练摘要，以及10月8日至16日的完整训练与动作记录。9月30日至10月7日因更换健身房且记录残缺，不纳入力量、训练量和进步速度的直接比较，但不排除该阶段对恢复与后续表现的影响。取得近期真实动作ID后，再定向提取历史相同动作，比较可比条件下的重量、次数、组数、单动作容量及单次训练总容量，关注整体趋势而非只挑最佳表现。考虑增肌期目前较短，区分短期训练适应、波动与可持续进步，不预设肌肉增长或进步速度已达到理想水平。'
    assert len(purpose) == 319
    capabilities = request_capabilities()
    assert len(purpose) <= capabilities['purpose']['maxLength'] == 500
    request = all_data_example()
    request['purpose'] = purpose
    request['datasets'] = [
        {'dataset_id': dataset_id, 'type': kind,
         'time_range': {'mode': 'explicit_range', 'start': start, 'end': end},
         'filters': {}, 'fields': list(DATASET_FIELDS[kind])}
        for dataset_id, kind, start, end in (
            ('body_transition', 'body', '2026-10-01', '2026-10-16'),
            ('diet_muscle_gain', 'diet', '2026-10-08', '2026-10-16'),
            ('training_baseline', 'training', '2026-09-01', '2026-09-29'),
            ('training_muscle_gain', 'training', '2026-10-08', '2026-10-16'),
            ('movement_muscle_gain', 'movement_progress', '2026-10-08', '2026-10-16'))]
    serialized = json.dumps(request, ensure_ascii=False)
    assert validate_request(json.loads(serialized)).valid
    # Concatenated complete objects are invalid even if the first one is valid.
    try:
        json.loads(serialized + serialized)
    except json.JSONDecodeError as error:
        assert error.msg == 'Extra data'
    else:
        raise AssertionError('Two request objects must not parse as one JSON')
    translated = copy.deepcopy(request)
    translated['目的'] = translated.pop('purpose')
    assert not validate_request(translated).valid
    protocol = AnalysisExportProtocolService(AnonymousFixtureProvider(
        ROOT / 'tools/fixtures/analysis_export_anonymous/fixture.json'))
    assert protocol.preview({'request': request})['status'] == 'preview_ready'
    prompt = build_initialization_prompt(themes=[], categories=[], modules=[], library_shape={})
    for guard in ('purpose.maxLength', '建议不超过200', 'U+0022', '不能翻译这些机器字面量',
                  '禁止接着输出第二个对象', '关闭网页自动翻译', '不把新旧对象拼接'):
        assert guard in prompt, guard


if __name__ == '__main__':
    for test in (test_all_data_round_trip, test_capabilities_cover_runtime_contract, test_prompt_boundaries,
                 test_failed_comparison_request_is_not_silently_accepted,
                 test_capability_snapshot_tracks_current_contract,
                 test_real_complex_request_and_serialization_guards):
        test()
        print(f'PASS {test.__name__}')
