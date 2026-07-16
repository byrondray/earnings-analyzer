FROM node:22-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_CLERK_PUBLISHABLE_KEY
ENV VITE_CLERK_PUBLISHABLE_KEY=$VITE_CLERK_PUBLISHABLE_KEY
RUN npm run build

FROM python:3.12-slim

RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

WORKDIR /app

COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir .

COPY backend/ ./

COPY --from=frontend-build /app/frontend/dist ./static

RUN chown -R appuser:appuser /app

USER appuser

ENV PORT=8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
