"""Anonymous semantic regressions, including optional isolated-model replay."""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.analysis_export_request import DATASET_FIELDS, validate_request
from fitness_ledger_core.restricted_export_integration import compile_natural_language_export
from fitness_ledger_core.restricted_export_parser_v3 import RestrictedExportParser
from tools.restricted_export_integration_test import fake_views
from web_desktop.backend.analysis_export_protocol import AnalysisExportProtocolService, AnonymousFixtureProvider

FIXTURE = ROOT / 'tools/fixtures/analysis_export_anonymous/fixture.json'


def round_trip(request: dict) -> dict:
    assert validate_request(request).valid
    protocol = AnalysisExportProtocolService(AnonymousFixtureProvider(FIXTURE))
    preview = protocol.preview({'request': request})
    assert preview['status'] == 'preview_ready', preview
    exported = protocol.export({'request': request, 'confirmed': True,
                               'confirmation_token': preview['confirmation_token']})
    assert exported['status'] == 'bundle_ready', exported
    bundle = json.loads(protocol.artifact(exported['artifact_id'], 'json')[1])
    assert bundle['safety_flags'] == {'raw_included': False, 'executor_called': False, 'formal_data_written': False}
    assert len(bundle['records']) == exported['record_count'] == preview['preview']['record_count']
    for format_name in request['output']['formats']:
        assert protocol.artifact(exported['artifact_id'], format_name)
    return bundle


def check_relation(bundle: dict, latest_count: int | None = 3) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding='utf-8'))
    training = [row for row in bundle['records'] if row['type'] == 'training']
    diet = [row for row in bundle['records'] if row['type'] == 'diet']
    expected_dates = sorted({row['date'] for row in fixture['datasets']['training']})
    if latest_count is not None:
        expected_dates = expected_dates[-latest_count:]
    assert sorted({row['date'] for row in training}) == expected_dates
    available_diet = {row['date'] for row in fixture['datasets']['diet']}
    expected = {(target, (date.fromisoformat(target) - timedelta(days=offset)).isoformat())
                for target in expected_dates for offset in (1, 2, 3)
                if (date.fromisoformat(target) - timedelta(days=offset)).isoformat() in available_diet}
    actual = {(row['relation']['target_session_date'], row['date']) for row in diet}
    assert actual == expected, (actual, expected)


def test_semantics() -> None:
    views = fake_views()
    try:
        for text in ('提取过去一周的全部数据', '提取过去一个星期全部数据'):
            result = compile_natural_language_export(views, text)
            assert result['status'] == 'ready'
            datasets = result['requests'][0]['datasets']
            assert {row['type'] for row in datasets} == set(DATASET_FIELDS)
            assert all(row['time_range'] == {'mode': 'recent_days', 'days': 7} for row in datasets)
            assert all('notes_scope' not in row for row in datasets)
            round_trip(result['requests'][0])
        only = compile_natural_language_export(views, '提取过去一周全部数据但只要体重')
        datasets = only['requests'][0]['datasets']
        assert len(datasets) == 1 and datasets[0]['fields'] == ['date', 'weight_kg'], datasets
        assert datasets[0]['time_range'] == {'mode': 'recent_days', 'days': 7}
        for text in ('提取过去一周体重和饮食', '提取这几天体重和饮食'):
            shared = compile_natural_language_export(views, text)['requests'][0]['datasets']
            assert {row['type'] for row in shared} == {'body', 'diet'}
            assert all(row['time_range'] == {'mode': 'recent_days', 'days': 7} for row in shared)
        excluded = compile_natural_language_export(views, '提取过去一周全部数据，不要体重和饮食')
        datasets = excluded['requests'][0]['datasets']
        assert all(row['type'] != 'diet' for row in datasets)
        body = next(row for row in datasets if row['type'] == 'body')
        assert 'weight_kg' not in body['fields'] and 'cardio_summary' in body['fields']
        for text in ('最近三次训练和每次训练前三天的饮食', '最近三次训练和每次训练之前三天饮食'):
            result = compile_natural_language_export(views, text)
            assert result['status'] == 'ready', result
            check_relation(round_trip(result['requests'][0]))
        thirty_days = compile_natural_language_export(views, '最近30天训练和训练前3天饮食')
        check_relation(round_trip(thirty_days['requests'][0]), latest_count=None)
        for text in ('最近30天训练和训练前后三天饮食', '最近三次训练和每次训练后三天饮食', '提取过去一周睡眠和体重', '提取过去半年全部数据', '提取最近三次全部数据', '提取全部数据'):
            result = compile_natural_language_export(views, text)
            assert result['status'] == 'needs_clarification' and not result['requests'], result
        assert compile_natural_language_export(views, '导出原始记录')['status'] == 'unsupported'
        parser = RestrictedExportParser([], reference_date=date(2026, 10, 15))
        for text, expected in [('导出上上周体重', ('2026-09-28', '2026-10-04')),
                               ('导出从上周到今天的体重', ('2026-10-05', '2026-10-15'))]:
            scope = parser.parse(text).dataset_intents[0].time_scope
            assert (scope.start, scope.end) == expected
    finally:
        views.close()


def replay_model_responses(path: Path) -> None:
    responses = json.loads(path.read_text(encoding='utf-8'))
    for key in ('A', 'B', 'E'):
        bundle = round_trip(responses[key])
        if key == 'A':
            assert bundle['records']
            assert {row['type'] for row in bundle['records']} == set(DATASET_FIELDS)
            assert all('2099-12-25' <= row['date'] <= '2099-12-31' for row in bundle['records'])
        elif key == 'B':
            check_relation(bundle)
        else:
            # This fixture has Synthetic Row only on Dec 14, outside the
            # requested latest 14-day window ending Dec 31. Empty is correct.
            assert not bundle['records'] and bundle['missing_information']
            assert responses[key]['datasets'][0]['filters']['movement_selector'] == {
                'kind': 'movement_name', 'value': 'synthetic row',
            }
        print(f'PASS isolated_model_{key}: validated, previewed, confirmed, artifact content checked')
    assert isinstance(responses['C'], str) and '？' in responses['C']
    assert isinstance(responses['D'], str) and '不支持' in responses['D']
    print('PASS isolated_model_C_D: clarification and unsupported-field boundary')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--responses', type=Path)
    args = parser.parse_args()
    test_semantics()
    print('PASS conversational_export_semantics')
    if args.responses:
        replay_model_responses(args.responses)
