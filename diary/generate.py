#!/usr/bin/env python3
"""Generate daily diary pages for the next N days.
Usage: python3 generate.py [days_ahead] [days_behind]
Default: 7 days ahead, 7 behind from today.
"""
import sys, shutil, os
from datetime import date, timedelta

days_ahead = int(sys.argv[1]) if len(sys.argv) > 1 else 7
days_behind = int(sys.argv[2]) if len(sys.argv) > 2 else 7

script_dir = os.path.dirname(os.path.abspath(__file__))
template = os.path.join(script_dir, 'day.html')
today = date.today()

for offset in range(-days_behind, days_ahead + 1):
    d = today + timedelta(days=offset)
    dest = os.path.join(script_dir, f'{d.isoformat()}.html')
    if not os.path.exists(dest):
        shutil.copy2(template, dest)
        print(f'Created {d.isoformat()}.html')
    else:
        print(f'Exists  {d.isoformat()}.html')
