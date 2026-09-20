# syntax=docker/dockerfile:1
# Multi-stage build for the interferometry workbench.
# Targets: `api` (FastAPI), `web` (nginx + built React app), `verify` (acceptance).

########## API service ##########
FROM python:3.12-slim AS api
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY api/app ./app
COPY api/tests ./tests
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

########## Web frontend build ##########
FROM node:20-alpine AS web-build
WORKDIR /build
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

########## Web service (nginx) ##########
FROM nginx:1.27-alpine AS web
COPY web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=web-build /build/dist /usr/share/nginx/html
EXPOSE 80

########## Acceptance suite (real browser) ##########
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy AS verify
ENV PYTHONUNBUFFERED=1
WORKDIR /verify
COPY verify/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY verify/ ./
CMD ["pytest", "-v", "--tb=short"]
