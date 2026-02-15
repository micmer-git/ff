#!/usr/bin/env python3
"""Sync sleep & exercise data from Intervals.icu API to local JSON.

Usage: python3 sync_intervals.py [days_back] [days_ahead]
Default: 14 days back, 7 ahead.

Requires INTERVALS_API_KEY env var or reads from ../../TOOLS.md
Outputs: diary/data/intervals.json
"""
import json, os, sys, re
from datetime import date, timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import base64

ATHLETE_ID = "i302515"
BASE_URL = f"https://intervals.icu/api/v1/athlete/{ATHLETE_ID}"

def get_api_key():
    key = os.environ.get("INTERVALS_API_KEY")
    if key:
        return key
    # Try reading from TOOLS.md
    tools_paths = [
        os.path.join(os.path.dirname(__file__), '..', '..', '..', 'TOOLS.md'),
        os.path.expanduser('~/.openclaw/workspace/TOOLS.md'),
    ]
    for p in tools_paths:
        try:
            with open(p) as f:
                content = f.read()
            m = re.search(r'key:\s*\*\*.*?\*\*.*?\n\s*[-*]\s*[\w-]+.*?key:\s*(\S+)', content, re.IGNORECASE)
            if not m:
                m = re.search(r'2026-02-14 key:\s*(\S+)', content)
            if m:
                return m.group(1)
        except FileNotFoundError:
            continue
    raise RuntimeError("No API key found. Set INTERVALS_API_KEY env var.")

def api_get(endpoint, api_key):
    url = f"{BASE_URL}/{endpoint}"
    creds = base64.b64encode(f"API_KEY:{api_key}".encode()).decode()
    req = Request(url, headers={"Authorization": f"Basic {creds}"})
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        print(f"  API error {e.code} for {endpoint}", file=sys.stderr)
        return None

def main():
    days_back = int(sys.argv[1]) if len(sys.argv) > 1 else 14
    days_ahead = int(sys.argv[2]) if len(sys.argv) > 2 else 7

    api_key = get_api_key()
    today = date.today()
    oldest = (today - timedelta(days=days_back)).isoformat()
    newest = (today + timedelta(days=days_ahead)).isoformat()

    print(f"Syncing Intervals.icu data: {oldest} → {newest}")

    # Fetch wellness (sleep, HRV, etc.)
    print("  Fetching wellness...")
    wellness_raw = api_get(f"wellness?oldest={oldest}&newest={newest}", api_key)
    wellness = {}
    if wellness_raw:
        for w in wellness_raw:
            d = w.get("id", "")
            wellness[d] = {
                "sleepTime": w.get("sleepTime"),
                "sleepQuality": w.get("sleepQuality"),
                "hrv": w.get("hrv"),
                "restingHR": w.get("restingHR"),
                "weight": w.get("weight"),
                "ctl": w.get("ctl"),
                "atl": w.get("atl"),
                "mood": w.get("mood"),
                "motivation": w.get("motivation"),
                "readiness": w.get("readiness"),
            }
        print(f"    Got {len(wellness)} wellness records")

    # Fetch activities
    print("  Fetching activities...")
    activities_raw = api_get(f"activities?oldest={oldest}&newest={newest}", api_key)
    activities = {}
    if activities_raw:
        for a in activities_raw:
            d = a.get("start_date_local", "")[:10]
            if d not in activities:
                activities[d] = []
            activities[d].append({
                "type": a.get("type", ""),
                "name": a.get("name", ""),
                "moving_time": a.get("moving_time"),
                "elapsed_time": a.get("elapsed_time"),
                "distance": a.get("distance"),
                "icu_training_load": a.get("icu_training_load"),
                "icu_intensity": a.get("icu_intensity"),
                "average_heartrate": a.get("average_heartrate"),
                "calories": a.get("calories"),
                "pace": a.get("pace"),
            })
        total_acts = sum(len(v) for v in activities.values())
        print(f"    Got {total_acts} activities across {len(activities)} days")

    # Merge into per-day structure
    data = {}
    all_dates = set(wellness.keys()) | set(activities.keys())
    for d in sorted(all_dates):
        data[d] = {
            "wellness": wellness.get(d, {}),
            "activities": activities.get(d, []),
        }

    # Write output
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "intervals.json")
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"  Written to {out_path} ({len(data)} days)")

if __name__ == "__main__":
    main()
