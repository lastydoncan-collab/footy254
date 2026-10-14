# FOOTY254 AI

AI football match analysis and prediction: FastAPI backend, PostgreSQL, scikit-learn
model, React/Vite PWA dashboard, M-Pesa subscriptions.

The API and the dashboard are served **from one port, one origin** (`/api/...` is the
API, everything else is the app). That is what makes it run unchanged on phones,
tablets, laptops and as an installed PWA, with no addresses baked into the build.

---

## Quick start (Docker - recommended, any OS)

```bash
cp .env.example .env
#  edit .env:  FOOTY254_DB_PASSWORD, JWT_SECRET_KEY, FOOTBALL_API_KEY, MPESA_*...
#  generate secrets with:  python -c "import secrets; print(secrets.token_urlsafe(64))"
docker compose up -d --build
docker compose exec app python -m scripts.create_admin you@example.com
```

Open <http://localhost:8000>. The database schema is created automatically on first start,
and the first fixture sync runs ~45 seconds after boot.

**Testing from a phone on the same Wi-Fi over plain http** (`http://192.168.x.x:8000`):
browsers refuse `Secure` cookies on non-https addresses, so add `COOKIE_SECURE=false` to `.env`
(testing only).

### Public internet with automatic HTTPS

Point a DNS record at your server, then in `.env`:

```
DOMAIN=footy.example.com
FRONTEND_URL=https://footy.example.com
APP_BIND=127.0.0.1
FORWARDED_ALLOW_IPS=*
```
```bash
docker compose --profile https up -d --build
```
Caddy obtains and renews the certificate. Set
`MPESA_CALLBACK_URL=https://footy.example.com/api/mpesa/callback/{secret}`.

---

## Local development (no Docker)

Requirements: Python 3.11-3.12, Node 20+, PostgreSQL 14+.

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-backend.txt
cp .env.example .env                                   # fill in
python -m database.migrate                             # create/upgrade schema
python -m scripts.create_admin you@example.com
scripts/dev.sh                                         # Windows: scripts\dev.bat
```
API on :8000, dashboard on :5173 (reachable from other devices on your network).

Production without Docker: `cd footy254-dashboard && npm ci && npm run build`, then
`uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips=<your proxy IP>`.

---

## Authentication & authorization

* httpOnly cookies (JS cannot read tokens). 15-min access token, 30-day **rotating** refresh token.
* Refresh-token reuse detection: a replayed, already-rotated token revokes all of that user's
  sessions (with a short grace window so two browser tabs racing never log anyone out).
* bcrypt hashing with transparent upgrade of old hashes; existing users keep their passwords.
* Per-account lockout (5 failures -> 15 min, no account-existence leak) plus per-IP rate limits.
* Password policy (length, common-password and personal-info checks); changing/resetting a
  password instantly voids every existing session *and* access token.
* Disabled accounts lose access on their next request.
* CSRF defence (Origin check), strict security headers + CSP, no-store on API responses.
* Roles: `user`, subscriber (paid), `admin`. Admin API: `GET/PATCH /api/admin/users`,
  `POST /api/admin/users/{id}/revoke-sessions` (cannot demote yourself or the last admin).
  Create admins with `python -m scripts.create_admin <email>`.
* Sessions page (list devices, revoke one / all others / all).

## Configuration

See `.env.example` (every variable documented). Production refuses to start with a missing or weak
`JWT_SECRET_KEY`. Notable options: `ENABLE_DOCS`, `ENABLE_SCHEDULER`, `WEB_CONCURRENCY`, `DB_POOL_MAX`
(keep `workers x DB_POOL_MAX` below Postgres `max_connections`).

## Tests

```bash
python -m unittest discover -s tests -v
```
Runs without a database or network; tests needing an optional package skip themselves.

---

## What changed in this upgrade

**Defects that stopped the app working**

1. **Predictions could never be generated.** The engine produced 70 of the 75 features the shipped
   model expects (`home_defense` vs `home_defence`, plus Elo/encoder/recent-goal-difference features
   missing), so every prediction raised. Fixed and verified against the real model.
2. **No database schema existed** in the project (no migration created `users`, `fixtures`,
   `predictions`, `subscriptions`). Added `000_base_schema.sql` and a tracked migration runner that runs on startup.
3. **Frontend hard-coded `http://127.0.0.1:8000`** - broken on every device except the developer's PC. Now same-origin `/api`.
4. **"Log out this device" never worked** (a duplicate function with swapped arguments overrode the correct one).
5. **Fixture sync crashed** with `UnboundLocalError` whenever a competition request failed.
6. **App refused to boot** without `FOOTBALL_API_KEY` (raised at import).
7. **`/fixtures/finished` was unreachable** (shadowed by `/{match_id}`).
8. **Silent refresh skipped `/auth/me`**, so a page reload after 15 idle minutes logged users out despite a valid refresh cookie.
9. **passlib + current bcrypt crash** on register/login; replaced by direct bcrypt (old hashes still verify).
10. Wrong-password showed "Login required."; validation errors showed `[object Object]`; analytics blanked for free users; `scikit-learn` unpinned although the models need 1.8.0.

**Hardening / performance**: connection pooling (was one new Postgres connection per query),
gzip, in-memory caching for hot public reads, immutable asset caching, advisory-locked scheduler
(safe with multiple workers), hot-reload of a retrained model across workers, token/attempt housekeeping,
removal of a hard-coded database password (`database/db.py`), health endpoints that no longer leak internals.

## Known limitations

* Account lockout is per email: someone can deliberately lock a victim's account for 15 minutes
  (tunable with `MAX_FAILED_LOGINS` / `LOCKOUT_MINUTES`).
* There is no admin screen in the dashboard yet - use the admin API / CLI.
* Retraining runs inside the web process (as originally designed); on small servers move it to a separate job.
* The dashboard shows demo fixtures if the backend is unreachable (original behaviour, kept).
