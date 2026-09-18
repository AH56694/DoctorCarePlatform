FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY requirements.lock .
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY backend ./backend
COPY alembic.ini ./alembic.ini
COPY alembic.mysql.ini ./alembic.mysql.ini
COPY migrations ./migrations
COPY scripts/create-admin.py ./scripts/create-admin.py

RUN useradd --uid 10001 --create-home app
USER app

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
