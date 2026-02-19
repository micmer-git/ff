# Diary Nutrition API (cross-device sync)

Lightweight backend for syncing diary state across devices.

## Run

```bash
cd diary/api
node server.mjs
```

Optional env vars:

- `PORT` (default `8787`)
- `NUTRI_DB_PATH` (default `diary/api/nutrition-db.json`)
- `NUTRI_API_TOKEN` (optional Bearer auth)
- `NUTRI_INTERVALS_PATH` (default `diary/data/intervals.json`)
- `NUTRI_INTERVALS_SYNC_SCRIPT` (default `diary/sync_intervals.py`)
- `NUTRI_INTERVALS_ATHLETE` (for live Intervals.icu proxy)
- `NUTRI_INTERVALS_API_KEY` (for live Intervals.icu proxy)
- `NUTRI_MAX_BODY_BYTES` (payload limit, default `2000000`)

## Endpoints

- `GET /nutrition/day/YYYY-MM-DD`
- `PUT /nutrition/day/YYYY-MM-DD` with body:
- `GET /nutrition/intervals` (returns current `intervals.json` cache)
- `GET /nutrition/intervals/live?oldest=YYYY-MM-DD&newest=YYYY-MM-DD` (proxy live from Intervals.icu)
- `POST /nutrition/intervals/refresh` with optional body:
- `GET /nutrition/shared-db` (shared saved foods across devices)
- `PUT /nutrition/shared-db` with body:
- `POST /nutrition/shared-db/import-google-sheet` with body `{ "csv_url": "https://docs.google.com/.../export?format=csv" }`

```json
{ "days_back": 30, "days_ahead": 3 }
```

Requires `INTERVALS_API_KEY` in the server environment (or key resolution in `sync_intervals.py`).

```json
{ "state": { "log": [], "custom_foods": [] } }
```

```json
{ "shared": { "saved_foods": [] } }
```

## Connect from UI

In diary page header click `☁️` and set:
- Backend API base URL (e.g. `https://your-host`)
- optional token

Then the app will:
- pull day state from backend on load
- push state to backend on save
- pull/push shared saved foods library for cross-device quick-add
