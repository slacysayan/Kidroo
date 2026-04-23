# `apps/api/` — FastAPI backend

Python 3.11, FastAPI, deployed to Koyeb free tier.

Endpoints (see `docs/ARCHITECTURE.md`):
- `POST /jobs`
- `GET  /jobs/:id`
- `POST /jobs/:id/select`
- `POST /channels/connect`
- `GET  /channels/:id/health`

No WebSocket layer — realtime streaming is done via Supabase Realtime directly from the browser.

Scaffolding lands in Phase 1.
