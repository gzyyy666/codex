"""Replay isolated model replies against semantic expectations and the app.

The replies are produced outside this script by an independently initialized
LLM; this evaluator never repairs them or supplies answers to the model.
Only anonymous materialization fixtures are used.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.analysis_export_request import validate_request
from web_desktop.backend.analysis_export_protocol import AnalysisExportProtocolService, AnonymousFixtureProvider


def check_request(request: dict, days: int, types: set[str], *, allow_resolution: bool = False) -> dict:
    validation = validate_request(request)
    assert validation.valid, [error.to_dict() for error in validation.errors]
    assert {item['type'] for item in request['datasets']} == types, request
    for item in request['datasets']:
        assert item['time_range'] == {'mode': 'recent_days', 'days': days}, item
        selector = item['filters'].get('movement_selector', {})
        assert selector.get('kind') != 'movement_id', 'No user/catalog IDs were supplied in this experiment'
    if 'training' in types:
        training = next(item for item in request['datasets'] if item['type'] == 'training')
        assert {'date', 'standardized_summary', 'organization_relations'} <= set(training['fields'])
    if 'movement_progress' in types:
        movement = next(item for item in request['datasets'] if item['type'] == 'movement_progress')
        assert {'sets', 'segments', 'volume', 'total_reps'} <= set(movement['fields'])
    if 'diet' in types:
        diet = next(item for item in request['datasets'] if item['type'] == 'diet')
        assert {'calories_kcal', 'protein_g', 'carbs_g', 'fat_g', 'food_summary'} <= set(diet['fields'])
    protocol = AnalysisExportProtocolService(AnonymousFixtureProvider(
        ROOT / 'tools/fixtures/analysis_export_anonymous/fixture.json'))
    preview = protocol.preview({'request': request})
    if allow_resolution and preview['status'] == 'movement_resolution_required':
        # The anonymous catalog has no Chinese bench alias. This is the
        # correct controlled outcome, not a successful data export.
        assert preview['execution'] == {'executor_called': False, 'formal_data_written': False}
        return {'validation': 'valid', 'preview': 'movement_resolution_required', 'export': 'not_run'}
    assert preview['status'] == 'preview_ready', preview
    result = protocol.export({'request': request, 'confirmed': True,
                              'confirmation_token': preview['confirmation_token']})
    assert result['status'] == 'bundle_ready', result
    artifact = protocol.artifact(result['artifact_id'], 'json')
    bundle = json.loads(artifact[1])
    assert len(bundle['records']) == preview['preview']['record_count'] == result['record_count']
    assert bundle['safety_flags'] == {'raw_included': False, 'executor_called': False, 'formal_data_written': False}
    return {'validation': 'valid', 'export': result['status'], 'anonymous_records': len(bundle['records'])}


def evaluate(responses: dict) -> list[dict]:
    results = []
    complete_types = {'diet', 'training', 'movement_progress'}
    for key, days in [('A', 7), ('B', 7), ('C', 14)]:
        assert len(responses[key]) == 1
        result = check_request(responses[key][0], days, complete_types)
        assert result['anonymous_records'] > 0
        results.append({'case': key, **result})
    bench = responses['D'][0]
    assert isinstance(bench, dict), 'Known user-supplied name can be passed to Preview without inventing an ID'
    types = {item['type'] for item in bench['datasets']}
    assert types <= {'training', 'movement_progress'} and 'movement_progress' in types
    result = check_request(bench, 14, types, allow_resolution=True)
    selector = next(item for item in bench['datasets'] if item['type'] == 'movement_progress')['filters']['movement_selector']
    assert selector['kind'] == 'movement_name' and '卧推' in selector['value']
    results.append({'case': 'D', **result})
    assert len(responses['E']) == 2
    for index, (days, types) in enumerate([(14, complete_types), (30, {'training', 'movement_progress'})]):
        result = check_request(responses['E'][index], days, types)
        results.append({'case': f'E{index + 1}', **result})
    for key in ('F', 'G'):
        answer = responses[key][0]
        assert isinstance(answer, str) and ('？' in answer or '?' in answer), answer
        if key == 'F':
            assert '睡眠' in answer and ('不支持' in answer or '无法' in answer or '不能' in answer)
        results.append({'case': key, 'status': 'clarification', 'reply': answer})
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--responses', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    results = evaluate(json.loads(args.responses.read_text(encoding='utf-8')))
    report = {'status': 'PASS', 'kind': 'bounded isolated-model experiment, not a provider accuracy benchmark',
              'results': results}
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
