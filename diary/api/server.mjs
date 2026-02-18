#!/usr/bin/env node
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DB_PATH = process.env.NUTRI_DB_PATH || path.join(__dirname, 'nutrition-db.json');
const PORT = Number(process.env.PORT || 8787);
const API_TOKEN = process.env.NUTRI_API_TOKEN || '';

function readDb() {
  try { return JSON.parse(fs.readFileSync(DB_PATH, 'utf8')); } catch { return { days: {} }; }
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
    'Access-Control-Allow-Methods': 'GET, PUT, OPTIONS',
    'Cache-Control': 'no-store'
  });
  res.end(JSON.stringify(payload));
}
function authorized(req) {
  if (!API_TOKEN) return true;
  const auth = req.headers.authorization || '';
  return auth === `Bearer ${API_TOKEN}`;
}

const server = http.createServer((req, res) => {
  if (req.method === 'OPTIONS') return send(res, 204, {});
  if (!authorized(req)) return send(res, 401, { error: 'unauthorized' });

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
