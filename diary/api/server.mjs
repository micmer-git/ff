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
    proc.on('close', (code) => {
      if (code === 0) return resolve({ stdout, stderr });
      reject(new Error(`sync_intervals failed (${code})\n${stderr || stdout}`));
    });
  });
}

const server = http.createServer(async (req, res) => {
  if (req.method === 'OPTIONS') return send(res, 204, {});
  if (!authorized(req)) return send(res, 401, { error: 'unauthorized' });

  if (req.url === '/nutrition/intervals' && req.method === 'GET') {
    return send(res, 200, { intervals: readIntervals() });
  }

  if (req.url === '/nutrition/intervals/refresh' && req.method === 'POST') {
    let body = '';
    req.on('data', (c) => (body += c));
    req.on('end', async () => {
      let payload = {};
      try { payload = body ? JSON.parse(body) : {}; } catch { return send(res, 400, { error: 'invalid_json' }); }
      const daysBack = Number(payload.days_back ?? 30);
      const daysAhead = Number(payload.days_ahead ?? 3);
      try {
        const out = await runIntervalsSync(daysBack, daysAhead);
        const intervals = readIntervals();
        return send(res, 200, {
          ok: true,
          days_back: daysBack,
          days_ahead: daysAhead,
          synced_days: Object.keys(intervals).length,
          output: out.stdout.trim()
        });
      } catch (e) {
        return send(res, 500, { error: 'intervals_sync_failed', detail: String(e.message || e) });
      }
    });
    return;
  }

  if (req.url === '/nutrition/shared-db' && req.method === 'GET') {
    const db = readDb();
    return send(res, 200, { shared: db.shared });
  }

  if (req.url === '/nutrition/shared-db' && req.method === 'PUT') {
    let body = '';
    req.on('data', (c) => (body += c));
    req.on('end', () => {
      let payload;
      try { payload = JSON.parse(body || '{}'); } catch { return send(res, 400, { error: 'invalid_json' }); }
      if (!payload || typeof payload !== 'object' || !payload.shared || typeof payload.shared !== 'object') {
        return send(res, 400, { error: 'missing_shared' });
      }
      const db = readDb();
      const savedFoods = Array.isArray(payload.shared.saved_foods) ? payload.shared.saved_foods : db.shared.saved_foods;
      db.shared = {
        ...db.shared,
        ...payload.shared,
        saved_foods: savedFoods,
        updated_at: new Date().toISOString(),
      };
      writeDb(db);
      return send(res, 200, { ok: true, shared: db.shared });
    });
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
    let body = '';
    req.on('data', (c) => (body += c));
    req.on('end', () => {
      let payload;
      try { payload = JSON.parse(body || '{}'); } catch { return send(res, 400, { error: 'invalid_json' }); }
      if (!payload || typeof payload !== 'object' || !payload.state) return send(res, 400, { error: 'missing_state' });
      const db = readDb();
      db.days[day] = payload.state;
      writeDb(db);
      return send(res, 200, { ok: true, day });
    });
    return;
  }

  return send(res, 405, { error: 'method_not_allowed' });
});

server.listen(PORT, () => {
  console.log(`Nutrition API listening on :${PORT}`);
  console.log(`DB: ${DB_PATH}`);
  if (API_TOKEN) console.log('Auth: Bearer token enabled');
});
