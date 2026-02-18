# FF Diary — Engineering Review (Front-end / Back-end / UX)

Date: 2026-02-18

## Executive summary

High-impact architecture is now in place:
- Single-page day routing (`day.html?date=`)
- Cross-device day sync backend (`diary/api/server.mjs`)
- Live Intervals refresh flow + local fallback

This pass improves reliability and UX coherence by adding conflict-safe sync semantics, reduced button clutter, and visible sync state.

---

## Front-end review

### Strengths
- Good component split by feature area (Food, Nutrition, Checklists, Week)
- Strong local-first behavior (`localStorage`) with immediate responsiveness
- Practical data model (foods + recipe composition + per-part overrides)

### Risks found
- API save called on every small action without coalescing
- No clear user feedback for cloud sync state
- Potential stale overwrite across devices (last-write-wins without checks)
- Refresh controls duplicated in some flows

### Changes applied
- Added **sync status chip** in header (`Sync: local / cloud / failed`)
- Added **debounced cloud save** (coalesced writes)
- Added `_updatedAt` state timestamp
- Added stale-state conflict handling in UI path
- Removed duplicated refresh icon in header
- Reduced refresh clutter in wellness card (single top refresh control)

---

## Back-end review

### Strengths
- Minimal, deployable API footprint
- Supports day sync + shared foods + intervals refresh bridge
- Optional bearer token auth

### Risks found
- No request payload-size guard
- No stale-write protection on day state
- No health endpoint for runtime checks

### Changes applied
- Added request JSON parser with **payload size cap** (`NUTRI_MAX_BODY_BYTES`)
- Added `/health` endpoint
- Added conflict guard on `PUT /nutrition/day/:day`:
  - compares incoming `_updatedAt` vs stored
  - returns `409 stale_state` when payload is older

---

## UX review

### Current direction
- Much cleaner than previous (single nutrition tab, checklists merged)
- Better add-food visual consistency

### Changes applied in this pass
- Single explicit refresh control in header (no duplicate icon)
- Sync visibility surfaced to user (status chip)

### Next 100x opportunities (recommended)
1. Undo history stack (multi-step)
2. Offline queue + retry/backoff policy for API sync
3. Date-range compare view (week over week)
4. Filtered food catalog search bar with favorites
5. “Today plan” mode (preload recurring + checklist targets)

---

## Operational recommendation

Treat this as the new reliability baseline:
- Local-first + debounced sync + conflict-safe backend
- Keep Intervals refresh explicit and singular
- Continue shipping UX improvements in small reviewable PRs
