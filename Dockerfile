# syntax=docker/dockerfile:1

# ---------- 1. Build the React dashboard ----------
FROM node:22-alpine AS web
WORKDIR /web
COPY footy254-dashboard/package.json footy254-dashboard/package-lock.json ./
RUN npm ci
COPY footy254-dashboard/ ./
RUN npm run build

# ---------- 2. Python runtime: API + built dashboard on ONE port ----------
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production \
    PORT=8000 \
    WEB_CONCURRENCY=2 \
    FORWARDED_ALLOW_IPS=127.0.0.1

RUN useradd --create-home --uid 10001 app
WORKDIR /app

COPY requirements-backend.txt .
RUN pip install -r requirements-backend.txt

COPY --chown=app:app . .
COPY --from=web --chown=app:app /web/dist ./footy254-dashboard/dist

# The app retrains models and rewrites data files at runtime.
RUN chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT','8000'), timeout=4)"

# --proxy-headers + --forwarded-allow-ips make request.client the REAL visitor
# behind Caddy/nginx/a cloud load balancer, so per-IP rate limits work per user.
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers ${WEB_CONCURRENCY} --proxy-headers --forwarded-allow-ips=${FORWARDED_ALLOW_IPS}"]
