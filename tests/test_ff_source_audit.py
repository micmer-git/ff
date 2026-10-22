import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ff_source_audit import source_key, contains_source, audit


class SourceAuditTest(unittest.TestCase):
    def test_x_aliases_and_media_urls(self):
        self.assertEqual(source_key('https://twitter.com/i/status/123?s=20'),
                         source_key('https://x.com/person/status/123/photo/1'))
        self.assertTrue(contains_source({'html': '<div data-id="123">'}, 'https://x.com/p/status/123'))
        self.assertFalse(contains_source({'id': '1234'}, 'https://x.com/p/status/123'))

    def test_url_boundaries_and_tracking(self):
        record = {'html': '<a href="https://site.test/part-10?utm_source=x">link</a>'}
        self.assertFalse(contains_source(record, 'https://site.test/part-1'))
        self.assertTrue(contains_source(record, 'https://site.test/part-10'))

    def test_reserved_is_not_published_and_share_date_is_not_publication(self):
        notes = [{'id': 1, 'url': 'https://site.test/new', 'source_timestamp': '2026-10-22'},
                 {'id': 2, 'url': 'https://site.test/old'}]
        decisions = [{'url': notes[1]['url'], 'published_date': '2026-03-01', 'status': 'available'}]
        rows = audit(notes, [], decisions, '2026-07-01')
        self.assertEqual(rows[0]['status'], 'unmatched_needs_review')
        self.assertEqual(rows[1]['status'], 'outside_window')
        decision = [{'url': notes[0]['url'], 'status': 'reserved_draft', 'draft_url': 'draft'}]
        self.assertEqual(audit(notes, [], decision, '2026-07-01')[0]['status'], 'reserved_draft')
        self.assertEqual(audit(notes, [{'url': notes[0]['url']}], decision, '2026-07-01')[0]['status'], 'published_match')


if __name__ == '__main__':
    unittest.main()
