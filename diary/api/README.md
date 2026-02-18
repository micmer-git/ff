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

## Endpoints

- `GET /nutrition/day/YYYY-MM-DD`
- `PUT /nutrition/day/YYYY-MM-DD` with body:

```json
{ "state": { "log": [], "custom_foods": [] } }
```

## Connect from UI

In diary page header click `☁️` and set:
- Backend API base URL (e.g. `https://your-host`)
- optional token

Then the app will:
- pull day state from backend on load
- push state to backend on save

