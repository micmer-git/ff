#!/usr/bin/env node
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DIARY_ROOT = path.resolve(__dirname, '..');
const DB_PATH = process.env.NUTRI_DB_PATH || path.join(__dirname, 'nutrition-db.json');
const INTERVALS_PATH = process.env.NUTRI_INTERVALS_PATH || path.join(DIARY_ROOT, 'data', 'intervals.json');
const INTERVALS_SYNC_SCRIPT = process.env.NUTRI_INTERVALS_SYNC_SCRIPT || path.join(DIARY_ROOT, 'sync_intervals.py');
const PORT = Number(process.env.PORT || 8787);
const API_TOKEN = process.env.NUTRI_API_TOKEN || '';
const MAX_BODY_BYTES = Number(process.env.NUTRI_MAX_BODY_BYTES || 2_000_000);
const INTERVALS_ATHLETE = process.env.NUTRI_INTERVALS_ATHLETE || '';
const INTERVALS_API_KEY = process.env.NUTRI_INTERVALS_API_KEY || process.env.INTERVALS_API_KEY || '';

function readDb() {
  let db;
  try { db = JSON.parse(fs.readFileSync(DB_PATH, 'utf8')); } catch { db = {}; }
  if (!db || typeof db !== 'object') db = {};
  if (!db.days || typeof db.days !== 'object') db.days = {};
  if (!db.shared || typeof db.shared !== 'object') db.shared = {};
  if (!Array.isArray(db.shared.saved_foods)) db.shared.saved_foods = [];
  return db;
}
function writeDb(db) {
  fs.mkdirSync(path.dirname(DB_PATH), { recursive: true });
  fs.writeFileSync(DB_PATH, JSON.stringify(db, null, 2));
}
function send(res, status, payload) {
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Allow-Methods': 'GET, PUT, POST, OPTIONS',
    'Cache-Control': 'no-store'
  });
  res.end(JSON.stringify(payload));
}
function authorized(req) {
  if (!API_TOKEN) return true;
  const auth = req.headers.authorization || '';
  return auth === `Bearer ${API_TOKEN}`;
}
function readIntervals() {
  try { return JSON.parse(fs.readFileSync(INTERVALS_PATH, 'utf8')); } catch { return {}; }
}
function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    let size = 0;
    req.on('data', (c) => {
      size += c.length;
      if (size > MAX_BODY_BYTES) {
        reject(new Error('payload_too_large'));
        req.destroy();
        return;
      }
      body += c;
    });
    req.on('end', () => {
      try { resolve(body ? JSON.parse(body) : {}); }
      catch { reject(new Error('invalid_json')); }
    });
    req.on('error', reject);
  });
}

async function fetchIntervalsLive(oldest, newest) {
  if (!INTERVALS_ATHLETE || !INTERVALS_API_KEY) return { ok: false, error: 'missing_intervals_env' };
  const base = `https://intervals.icu/api/v1/athlete/${INTERVALS_ATHLETE}`;
  const auth = 'Basic ' + Buffer.from(`API_KEY:${INTERVALS_API_KEY}`).toString('base64');
  const headers = { Authorization: auth };
  const [wResp, aResp] = await Promise.all([
    fetch(`${base}/wellness?oldest=${oldest}&newest=${newest}`, { headers }),
    fetch(`${base}/activities?oldest=${oldest}&newest=${newest}`, { headers })
  ]);
  if (!wResp.ok || !aResp.ok) return { ok: false, error: 'intervals_http_error', statusWellness: wResp.status, statusActivities: aResp.status };

  const wellnessRaw = await wResp.json();
  const actsRaw = await aResp.json();
  const out = {};

  for (const w of (wellnessRaw || [])) {
    const d = w.id;
    if (!d) continue;
    if (!out[d]) out[d] = { wellness: {}, activities: [] };
    out[d].wellness = {
      sleepTime: w.sleepTime, sleepQuality: w.sleepQuality, hrv: w.hrv, restingHR: w.restingHR,
      weight: w.weight, ctl: w.ctl, atl: w.atl, mood: w.mood, motivation: w.motivation, readiness: w.readiness,
    };
  }
  for (const a of (actsRaw || [])) {
    const d = (a.start_date_local || '').slice(0, 10);
    if (!d) continue;
    if (!out[d]) out[d] = { wellness: {}, activities: [] };
    out[d].activities.push({
      type: a.type || '', name: a.name || '', moving_time: a.moving_time, elapsed_time: a.elapsed_time,
      distance: a.distance, icu_training_load: a.icu_training_load, icu_intensity: a.icu_intensity,
      average_heartrate: a.average_heartrate, calories: a.calories, pace: a.pace,
      total_elevation_gain: a.total_elevation_gain, elevation_gain: a.elevation_gain,
    });
  }
  return { ok: true, data: out };
}

function runIntervalsSync(daysBack = 30, daysAhead = 3) {
  return new Promise((resolve, reject) => {
    const proc = spawn('python3', [INTERVALS_SYNC_SCRIPT, String(daysBack), String(daysAhead)], {
      cwd: DIARY_ROOT,
      env: process.env,
      stdio: ['ignore', 'pipe', 'pipe']
    });
    let stdout = '';
    let stderr = '';
    proc.stdout.on('data', (d) => { stdout += String(d); });
    proc.stderr.on('data', (d) => { stderr += String(d); });
    proc.on('error', reject);
    proc.on('close', (code) => code === 0 ? resolve({ stdout, stderr }) : reject(new Error(`sync_intervals failed (${code})\n${stderr || stdout}`)));
  });
}

const server = http.createServer(async (req, res) => {
  if (req.method === 'OPTIONS') return send(res, 204, {});
  if (!authorized(req)) return send(res, 401, { error: 'unauthorized' });

  if (req.url === '/health' && req.method === 'GET') return send(res, 200, { ok: true, service: 'nutrition-api' });

  if (req.url === '/nutrition/intervals' && req.method === 'GET') return send(res, 200, { intervals: readIntervals(), source: 'file_cache' });

  if (req.url.startsWith('/nutrition/intervals/live') && req.method === 'GET') {
    const u = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
    const oldest = u.searchParams.get('oldest') || new Date(Date.now() - 35 * 86400000).toISOString().slice(0, 10);
    const newest = u.searchParams.get('newest') || new Date(Date.now() + 2 * 86400000).toISOString().slice(0, 10);
    try {
      const live = await fetchIntervalsLive(oldest, newest);
      if (!live.ok) return send(res, 502, live);
      return send(res, 200, { intervals: live.data, source: 'intervals_live', oldest, newest });
    } catch (e) {
      return send(res, 500, { error: 'intervals_live_failed', detail: String(e.message || e) });
    }
  }

  if (req.url === '/nutrition/intervals/refresh' && req.method === 'POST') {
    (async () => {
      let payload = {};
      try { payload = await readJsonBody(req); }
      catch (e) {
        if (String(e.message) === 'payload_too_large') return send(res, 413, { error: 'payload_too_large' });
        return send(res, 400, { error: 'invalid_json' });
      }
      const daysBack = Number(payload.days_back ?? 30);
      const daysAhead = Number(payload.days_ahead ?? 3);
      try {
        const out = await runIntervalsSync(daysBack, daysAhead);
        const intervals = readIntervals();
        return send(res, 200, { ok: true, days_back: daysBack, days_ahead: daysAhead, synced_days: Object.keys(intervals).length, output: out.stdout.trim() });
      } catch (e) {
        return send(res, 500, { error: 'intervals_sync_failed', detail: String(e.message || e) });
      }
    })();
    return;
  }

  if (req.url === '/nutrition/shared-db/import-google-sheet' && req.method === 'POST') {
    (async () => {
      let payload = {};
      try { payload = await readJsonBody(req); }
      catch (e) {
        if (String(e.message) === 'payload_too_large') return send(res, 413, { error: 'payload_too_large' });
        return send(res, 400, { error: 'invalid_json' });
      }
      const csvUrl = payload?.csv_url;
      if (!csvUrl || typeof csvUrl !== 'string' || !/^https:\/\//.test(csvUrl)) return send(res, 400, { error: 'invalid_csv_url' });
      try {
        const resp = await fetch(csvUrl);
        if (!resp.ok) return send(res, 502, { error: 'sheet_fetch_failed', status: resp.status });
        const txt = await resp.text();
        const lines = txt.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
        if (!lines.length) return send(res, 400, { error: 'empty_sheet' });
        const headers = lines[0].split(',').map((h) => h.trim().toLowerCase());
        const idxName = headers.indexOf('label') >= 0 ? headers.indexOf('label') : headers.indexOf('name');
        const idxKcal = headers.indexOf('kcal');
        const idxProt = headers.indexOf('protein_g');
        const idxCarb = headers.indexOf('carbs_g');
        const idxFat = headers.indexOf('fat_g');
        if (idxName < 0) return send(res, 400, { error: 'missing_label_column' });
        const foods = [];
        for (const line of lines.slice(1)) {
          const cols = line.split(',');
          const label = (cols[idxName] || '').trim();
          if (!label) continue;
          const key = label.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
          foods.push({
            id: `g_${key}`,
            emoji: '🧩',
            label,
            source: 'google_sheet',
            kcal: Number(cols[idxKcal] || 0) || 0,
            protein_g: Number(cols[idxProt] || 0) || 0,
            carbs_g: Number(cols[idxCarb] || 0) || 0,
            fat_g: Number(cols[idxFat] || 0) || 0,
          });
        }
        const db = readDb();
        db.shared.saved_foods = foods;
        db.shared.sheet_csv_url = csvUrl;
        db.shared.updated_at = new Date().toISOString();
        writeDb(db);
        return send(res, 200, { ok: true, imported: foods.length, shared: db.shared });
      } catch (e) {
        return send(res, 500, { error: 'sheet_import_failed', detail: String(e.message || e) });
      }
    })();
    return;
  }

  if (req.url === '/nutrition/shared-db' && req.method === 'GET') {
    const db = readDb();
    return send(res, 200, { shared: db.shared });
  }

  if (req.url === '/nutrition/shared-db' && req.method === 'PUT') {
    (async () => {
      let payload;
      try { payload = await readJsonBody(req); }
      catch (e) {
        if (String(e.message) === 'payload_too_large') return send(res, 413, { error: 'payload_too_large' });
        return send(res, 400, { error: 'invalid_json' });
      }
      if (!payload || typeof payload !== 'object' || !payload.shared || typeof payload.shared !== 'object') return send(res, 400, { error: 'missing_shared' });
      const db = readDb();
      const savedFoods = Array.isArray(payload.shared.saved_foods) ? payload.shared.saved_foods : db.shared.saved_foods;
      db.shared = { ...db.shared, ...payload.shared, saved_foods: savedFoods, updated_at: new Date().toISOString() };
      writeDb(db);
      return send(res, 200, { ok: true, shared: db.shared });
    })();
    return;
  }

  const m = req.url.match(/^\/nutrition\/day\/(\d{4}-\d{2}-\d{2})$/);
  if (!m) return send(res, 404, { error: 'not_found' });
  const day = m[1];

  if (req.method === 'GET') {
    const db = readDb();
    return send(res, 200, { day, state: db.days[day] || null });
  }

  if (req.method === 'PUT') {
    (async () => {
      let payload;
      try { payload = await readJsonBody(req); }
      catch (e) {
        if (String(e.message) === 'payload_too_large') return send(res, 413, { error: 'payload_too_large' });
        return send(res, 400, { error: 'invalid_json' });
      }
      if (!payload || typeof payload !== 'object' || !payload.state) return send(res, 400, { error: 'missing_state' });
      const db = readDb();
      const incoming = payload.state;
      const incomingTs = new Date(incoming?._updatedAt || 0).getTime();
      const current = db.days[day];
      const currentTs = new Date(current?._updatedAt || 0).getTime();
      if (current && incomingTs && currentTs && incomingTs < currentTs) return send(res, 409, { error: 'stale_state', day, current });
      db.days[day] = incoming;
      writeDb(db);
      return send(res, 200, { ok: true, day, updatedAt: incoming?._updatedAt || null });
    })();
    return;
  }

  return send(res, 405, { error: 'method_not_allowed' });
});

server.listen(PORT, () => {
  console.log(`Nutrition API listening on :${PORT}`);
  console.log(`DB: ${DB_PATH}`);
  if (API_TOKEN) console.log('Auth: Bearer token enabled');
});
