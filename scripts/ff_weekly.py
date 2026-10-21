"""Portable private intake helper; no network calls or publishing capabilities."""
import argparse
import datetime as dt
import json
from pathlib import Path
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]


def canonical_url(value):
    p = urlsplit(value)
    if p.scheme not in ('http', 'https') or not p.netloc:
        raise ValueError('Source URL must be absolute http(s)')
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in ('fbclid', 'gclid')]
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path, urlencode(query), p.fragment))


def init_issue(root, week):
    if not re.fullmatch(r'\d{4}-W\d{2}', week):
        raise ValueError('Expected ISO week YYYY-Www')
    year, number = week.split('-W')
    dt.date.fromisocalendar(int(year), int(number), 1)
    folder = root / 'issues' / week
    folder.mkdir(parents=True, exist_ok=True)
    manifest = folder / 'manifest.json'
    if not manifest.exists():
        with manifest.open('x', encoding='utf-8') as stream:
            json.dump({'week': week, 'status': 'collecting', 'draft_url': None,
                       'used_source_ids': [], 'verified_at': None}, stream, indent=2)
    return manifest


def merge_records(existing, incoming):
    records = {item['id']: item for item in existing}
    if len(records) != len(existing):
        raise ValueError('Existing inbox has duplicate IDs; reconcile before import')
    for raw in incoming:
        item = dict(raw)
        for field in ('id', 'source_url', 'summary', 'shared_date', 'reading_status'):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError('Missing nonempty string: ' + field)
        dt.date.fromisoformat(item['shared_date'])
        item['canonical_url'] = canonical_url(item['source_url'])
        if item['id'] in records:
            previous = {k: v for k, v in records[item['id']].items() if k != 'duplicate_of'}
            if {k: v for k, v in item.items() if k != 'duplicate_of'} != previous:
                raise ValueError('Edited source needs manual reconciliation: ' + item['id'])
            continue
        duplicate = next((r['id'] for r in records.values()
                          if canonical_url(r['source_url']) == item['canonical_url']), None)
        if duplicate:
            item['duplicate_of'] = duplicate
        records[item['id']] = item
    return list(records.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-dir', type=Path, default=ROOT / 'editorial' / 'local')
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init')
    init.add_argument('--week', required=True)
    ingest = commands.add_parser('import')
    ingest.add_argument('file', type=Path, help='JSON array of source records')
    args = parser.parse_args()
    if args.command == 'init':
        print(init_issue(args.local_dir, args.week))
        return
    args.local_dir.mkdir(parents=True, exist_ok=True)
    target = args.local_dir / 'inbox.json'
    existing = json.loads(target.read_text(encoding='utf-8-sig')) if target.exists() else []
    incoming = json.loads(args.file.read_text(encoding='utf-8-sig'))
    if not isinstance(incoming, list):
        raise ValueError('Input must be a JSON array')
    merged = merge_records(existing, incoming)
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(target)
    print(f'{len(merged)} records saved; {len(merged) - len(existing)} added')


if __name__ == '__main__':
    main()
