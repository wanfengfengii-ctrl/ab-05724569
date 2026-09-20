# syntax=docker/dockerfile:1.7

# ---------- 前端构建 ----------
FROM node:22-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- Web：nginx 托管静态资源并反代 API ----------
FROM nginx:1.27-alpine AS web
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-builder /build/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s --retries=10 \
  CMD wget -qO- http://localhost:80/ >/dev/null 2>&1 || exit 1

# ---------- API：FastAPI + uvicorn（精确有理数解算） ----------
FROM python:3.12-slim AS api
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
RUN useradd --create-home --uid 10001 metrologist \
    && chown -R metrologist /app
USER metrologist
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=10 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status==200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------- verify：Playwright 真实浏览器验收（Chromium 已预装于基础镜像） ----------
FROM mcr.microsoft.com/playwright/python:v1.48.0-noble AS verify
WORKDIR /verify
COPY verify/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY verify/ ./
ENV BASE_URL=http://web:80 \
    API_URL=http://api:8000 \
    PYTHONUNBUFFERED=1
CMD ["pytest", "-q", "--tb=short", "e2e"]
