"""Bodyweight expressions must not become part of an inline movement name."""
from __future__ import annotations

import json
from pathlib import Path
import runpy
import sys
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from ledger_commands import LedgerCommandService

APP = runpy.run_path(PROJECT / 'stable_app.pyw')
DICTIONARY = {'version': '1', 'movements': [
    {'movement_id': 'TEST_PULL', 'display_name': '杠铃提拉', 'aliases': ['杠铃提拉'], 'muscle_group': 'shoulders', 'active': True},
    {'movement_id': 'TEST_DIP', 'display_name': '双杠臂屈伸', 'aliases': ['双杠臂屈伸'], 'muscle_group': 'chest', 'active': True},
    {'movement_id': 'TEST_FLY', 'display_name': '器械飞鸟', 'aliases': ['器械飞鸟'], 'muscle_group': 'shoulders', 'active': True},
]}


def parser():
    instance = APP['FitnessTrackerApp'].__new__(APP['FitnessTrackerApp'])
    instance.movement_dictionary = DICTIONARY
    instance.movement_definitions_by_id, instance.movement_definitions_by_alias = APP['movement_definition_index'](DICTIONARY)
    return instance


def raw(numbered=False):
    prefixes = ['1. ', '2. ', '3. '] if numbered else ['', '', '']
    return ('2099-01-01\ntraining: test\n'
            f' {prefixes[0]}杠铃提拉 40-12-1 40-10-2\n'
            f' {prefixes[1]}双杠臂屈伸 自重-10-2\n'
            ' notes: dip-only note\n'
            f' {prefixes[2]}器械飞鸟 70-12-2\n'
            ' notes: fly-only note\ntraining notes: session-only note')


class BodyweightInlineTest(unittest.TestCase):
    def test_bodyweight_names(self):
        for expression in ('自重-10-2', '自重 x 10 x 2', 'bodyweight-10-2', 'BODYWEIGHT × 10 × 2', '自重10次2组'):
            with self.subTest(expression=expression):
                self.assertEqual(APP['strip_movement_metrics']('双杠臂屈伸 ' + expression), '双杠臂屈伸')
                movements = parser().parse_entry('training: test\n 双杠臂屈伸 ' + expression)['training']['movements']
                self.assertEqual(movements[0]['movement_id'], 'TEST_DIP')
                label = '自重' if expression.startswith('自重') else expression.split('-')[0].split()[0]
                self.assertEqual(movements[0]['sets'], [{'weight': 0.0, 'weight_text': label, 'reps': 10, 'sets': 2}])

    def test_numbered_and_unnumbered_ownership(self):
        for numbered in (False, True):
            with self.subTest(numbered=numbered):
                training = parser().parse_entry(raw(numbered))['training']
                movements = training['movements']
                self.assertEqual([m['movement_id'] for m in movements], ['TEST_PULL', 'TEST_DIP', 'TEST_FLY'])
                self.assertEqual([sum(s['sets'] for s in m['sets']) for m in movements], [3, 2, 2])
                self.assertEqual([m['notes'] for m in movements], ['', 'dip-only note', 'fly-only note'])
                self.assertNotIn('双杠臂屈伸', movements[0]['raw'])
                self.assertEqual(training['notes'], 'session-only note')

    def test_existing_numeric_and_segmented_names(self):
        for name, expression in [('杠铃提拉', '40-12-3'), ('器械飞鸟', '(10+5)-(12+6)-2')]:
            self.assertEqual(APP['strip_movement_metrics'](name + ' ' + expression), name)

    def test_save_and_reload(self):
        with tempfile.TemporaryDirectory(prefix='fl-bodyweight-inline-') as temporary:
            root = Path(temporary)
            tracker, dictionary = root / 'tracker.json', root / 'dictionary.json'
            tracker.write_text(json.dumps({'daily_records': [], 'diet_records': [], 'training_sessions': [], 'movements': {}, 'raw_entries': []}), encoding='utf-8')
            dictionary.write_text(json.dumps(DICTIONARY, ensure_ascii=False), encoding='utf-8')
            service = LedgerCommandService(tracker, dictionary, root / 'backups', parser().parse_for_shared_service)
            result = service.save(service.parse(raw())['review'])
            self.assertEqual(result['status'], 'CREATED')
            stored = json.loads(tracker.read_text(encoding='utf-8'))
            items = stored['training_sessions'][0]['movement_items']
            self.assertEqual([sum(s['sets'] for s in i['sets']) for i in items], [3, 2, 2])
            self.assertEqual([i['notes'] for i in items], ['', 'dip-only note', 'fly-only note'])
            histories = [h for m in stored['movements'].values() if m['movement_id'] == 'TEST_DIP' for h in m['history']]
            self.assertEqual(len(histories), 1)
            self.assertEqual(histories[0]['sets'], items[1]['sets'])
            self.assertEqual(histories[0]['notes'], 'dip-only note')
            self.assertEqual(stored['raw_entries'][0]['text'], raw())


if __name__ == '__main__':
    unittest.main()
