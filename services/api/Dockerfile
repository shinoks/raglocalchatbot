FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*

COPY services/api/pyproject.toml /app/pyproject.toml
COPY services/api/alembic.ini /app/alembic.ini
COPY services/api/alembic /app/alembic
COPY services/api/app /app/app

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
