import copy
import json
import unittest
from pathlib import Path

from chapter1_adapter import normalize_initial_assignment


class ChapterHandoffTests(unittest.TestCase):
    def test_only_known_tasks_and_no_future_events_are_exported(self):
        source = json.loads((Path(__file__).resolve().parents[1] / 'fixtures' / 'control.json').read_text())
        snapshot = normalize_initial_assignment(source)
        self.assertEqual(len(snapshot['known_tasks']), 4)
        self.assertNotIn('disturbances', snapshot)
        self.assertNotIn('tasks', snapshot)
        self.assertEqual(snapshot['source'], 'synthetic_initial_assignment')
        self.assertEqual(snapshot['time'], 0)

    def test_hidden_order_metadata_does_not_change_initial_handoff(self):
        source = json.loads((Path(__file__).resolve().parents[1] / 'fixtures' / 'control.json').read_text())
        altered = copy.deepcopy(source)
        for task in altered['tasks']:
            if not task['known_initial']:
                task['priority'] += 4
                task['quantity'] += 1
        self.assertEqual(normalize_initial_assignment(source), normalize_initial_assignment(altered))


if __name__ == '__main__':
    unittest.main()
