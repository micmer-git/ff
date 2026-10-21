import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('ff_weekly', Path(__file__).resolve().parents[1] / 'scripts/ff_weekly.py')
ff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ff)


class IntakeTests(unittest.TestCase):
    def test_semantic_queries_survive(self):
        self.assertEqual(ff.canonical_url('https://example.com/p?id=12&utm_source=x#figure'),
                         'https://example.com/p?id=12#figure')
        self.assertNotEqual(ff.canonical_url('https://example.com/p?id=12'),
                            ff.canonical_url('https://example.com/p?id=13'))

    def test_retry_and_conflict(self):
        row = dict(id='one', source_url='https://example.com/a', summary='A',
                   shared_date='2026-10-21', reading_status='unread')
        first = ff.merge_records([], [row])
        self.assertEqual(ff.merge_records(first, [row]), first)
        with self.assertRaises(ValueError):
            ff.merge_records(first, [dict(row, summary='Edited')])
        second = ff.merge_records(first, [dict(row, id='two')])
        self.assertEqual(second[1]['duplicate_of'], 'one')
        self.assertEqual(ff.merge_records(second, [dict(row, id='two')]), second)

    def test_init_preserves_draft(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = ff.init_issue(root, '2026-W43')
            path.write_text('{"draft_url":"saved"}', encoding='utf-8')
            ff.init_issue(root, '2026-W43')
            self.assertIn('saved', path.read_text())
            with self.assertRaises(ValueError):
                ff.init_issue(root, '../escape')
            with self.assertRaises(ValueError):
                ff.init_issue(root, '2026-W99')


if __name__ == '__main__':
    unittest.main()
