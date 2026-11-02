# Stage 1: build the web app with Node. Only the built files leave this stage.
FROM node:26.13.0-slim AS frontend

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Stage 2: the Python image that runs the API and serves the built web app
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY db ./db
COPY --from=frontend /frontend/dist ./frontend/dist

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

CMD ["sh", "-c", "python -m app.db && (python -m app.backfill_embeddings || echo 'Embedding backfill skipped') && (python -m app.demo || echo 'Demo cleanup skipped') && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]