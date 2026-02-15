#!/usr/bin/env python3
"""Generate daily diary pages from day.html template.
Usage: python3 generate.py [days_ahead] [days_behind] [--force]
Default: 14 days ahead, 14 behind from today.
--force: overwrite existing pages with new template.
"""
import sys, shutil, os
from datetime import date, timedelta

days_ahead = 14
days_behind = 14
force = '--force' in sys.argv

for arg in sys.argv[1:]:
    if arg == '--force':
        continue
    try:
        v = int(arg)
        if days_ahead == 14 and not any(a.isdigit() for a in sys.argv[1:sys.argv.index(arg)]):
            days_ahead = v
        else:
            days_behind = v
    except ValueError:
        pass

script_dir = os.path.dirname(os.path.abspath(__file__))
template = os.path.join(script_dir, 'day.html')
today = date.today()

if not os.path.exists(template):
    print(f'ERROR: Template {template} not found!')
    sys.exit(1)

created = 0
updated = 0
skipped = 0

for offset in range(-days_behind, days_ahead + 1):
    d = today + timedelta(days=offset)
    dest = os.path.join(script_dir, f'{d.isoformat()}.html')
    if not os.path.exists(dest):
        shutil.copy2(template, dest)
        print(f'Created {d.isoformat()}.html')
        created += 1
    elif force:
        shutil.copy2(template, dest)
        print(f'Updated {d.isoformat()}.html')
        updated += 1
    else:
        skipped += 1

# Also regenerate any existing dated pages outside the range
if force:
    import glob
    pattern = os.path.join(script_dir, '2???-??-??.html')
    for f in sorted(glob.glob(pattern)):
        basename = os.path.basename(f)
        if basename == 'day.html' or basename == 'index.html' or basename == '404.html':
            continue
        try:
            date.fromisoformat(basename.replace('.html', ''))
        except ValueError:
            continue
        # Check if already handled
        d = date.fromisoformat(basename.replace('.html', ''))
        if today - timedelta(days=days_behind) <= d <= today + timedelta(days=days_ahead):
            continue  # Already handled above
        shutil.copy2(template, f)
        print(f'Updated {basename} (outside range)')
        updated += 1

print(f'\nDone: {created} created, {updated} updated, {skipped} skipped')
