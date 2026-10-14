#!/usr/bin/env bash
# Local development: API on :8000 (auto-reload) + Vite dev server on :5173.
set -e
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "Copy .env.example to .env and fill it in first."; exit 1; }
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
API=$!
trap 'kill $API 2>/dev/null' EXIT
cd footy254-dashboard
[ -d node_modules ] || npm install
npm run dev
