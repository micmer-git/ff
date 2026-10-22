"""Reconcile saved notes with publication snapshots and explicit editorial decisions.

Read-only inputs; writes a private ledger. No network, browser or publishing API.
An unmatched URL is not proof that a topic has never appeared in the newsletter.
"""
import argparse
import datetime as dt
import html
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit, parse_qsl, urlencode


def source_key(url):
    p = urlsplit(html.unescape(url.strip()))
    host = p.netloc.lower().removeprefix('www.')
    if host in ('x.com', 'twitter.com', 'mobile.twitter.com'):
        match = re.search(r'/status/(\d+)', p.path)
        if match:
            return 'x:' + match[1]
    if host == 'youtu.be':
        return 'youtube:' + p.path.strip('/')
    if host in ('youtube.com', 'youtube-nocookie.com'):
        query = dict(parse_qsl(p.query))
        if query.get('v'):
            return 'youtube:' + query['v']
        match = re.match(r'/(?:embed|shorts)/([^/]+)', p.path)
        if match:
            return 'youtube:' + match[1]
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.startswith('utm_') and k not in ('fbclid', 'gclid')]
    return host + p.path.rstrip('/') + ('?' + urlencode(sorted(query)) if query else '')


def contains_source(record, url):
    text = html.unescape(unquote(json.dumps(record, ensure_ascii=False)))
    key = source_key(url)
    if key.startswith(('x:', 'youtube:')):
        return bool(re.search(r'(?<![\w-])' + re.escape(key.split(':', 1)[1]) + r'(?![\w-])', text))
    # Extract URL values from both HTML and JSON snapshots. Do not substring-match
    # article slugs: /part-1 must not match /part-10.
    urls = re.findall(r'https?://[^\s<>"\\]+', text)
    return any(source_key(candidate.rstrip("'),;")) == key for candidate in urls)


def audit(notes, published, decisions, since):
    dt.date.fromisoformat(since)
    by_key = {source_key(x['url']): x for x in decisions}
    # Parse each publication once, not once per saved note.
    index = []
    for record in published:
        text = html.unescape(unquote(json.dumps(record, ensure_ascii=False)))
        keys = {source_key(u.rstrip("'),;")) for u in re.findall(r'https?://[^\s<>"\\]+', text)}
        index.append((record, text, keys))
    rows = []
    for note in notes:
        url = note.get('url', '')
        if not url:
            continue
        decision = by_key.get(source_key(url), {})
        key = source_key(url)
        identifier = key.split(':', 1)[1] if key.startswith(('x:', 'youtube:')) else None
        pattern = re.compile(r'(?<![\w-])' + re.escape(identifier) + r'(?![\w-])') if identifier else None
        matches = [p.get('url') or p.get('title') or 'archive record'
                   for p, text, keys in index if key in keys or (pattern and pattern.search(text))]
        date = decision.get('published_date')
        if date:
            dt.date.fromisoformat(date)
        status = 'unmatched_needs_review'
        if matches:
            status = 'published_match'
        elif date and date < since:
            status = 'outside_window'
        elif decision.get('status'):
            status = decision['status']
        rows.append({'note_id': note.get('id'), 'title': note.get('title'),
                     'url': url, 'key': source_key(url), 'status': status,
                     'published_date': date, 'shared_date': note.get('source_timestamp'),
                     'publication_matches': matches,
                     'draft_url': decision.get('draft_url'),
                     'reason': decision.get('reason', 'Original date and topic reuse require review')})
    return rows


def records(path, key=None):
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if isinstance(data, list):
        return data
    if key and key in data:
        return data[key]
    return data.get('publications', [])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--notes', type=Path, required=True)
    parser.add_argument('--published', type=Path, action='append', required=True)
    parser.add_argument('--decisions', type=Path, required=True)
    parser.add_argument('--since', required=True, help='Original publication cutoff, YYYY-MM-DD')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    pubs = [r for path in args.published for r in records(path)]
    rows = audit(records(args.notes, 'notes'), pubs, records(args.decisions), args.since)
    counts = {s: sum(r['status'] == s for r in rows) for s in sorted({r['status'] for r in rows})}
    result = {'checked_at': dt.datetime.now(dt.timezone.utc).isoformat(),
              'since': args.since, 'coverage_files': [str(p) for p in args.published],
              'limits': 'Exact source matches only. Unmatched is not confirmed unused. Review topics and all drafts.',
              'counts': counts, 'notes': rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(counts))


if __name__ == '__main__':
    main()
