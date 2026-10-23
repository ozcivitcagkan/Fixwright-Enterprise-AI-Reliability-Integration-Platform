FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY db ./db

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

CMD ["sh", "-c", "python -m app.db && (python -m app.backfill_embeddings || echo 'Embedding backfill skipped') && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]