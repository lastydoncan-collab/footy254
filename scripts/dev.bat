@echo off
REM Local development on Windows: API on :8000 (auto-reload) + Vite on :5173.
cd /d "%~dp0.."
if not exist .env (echo Copy .env.example to .env and fill it in first. & exit /b 1)
start "FOOTY254 API" cmd /k python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
cd footy254-dashboard
if not exist node_modules call npm install
call npm run dev
