FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/tmp/huggingface

COPY python-service/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY python-service/ ./
RUN useradd --uid 10001 --create-home app \
    && mkdir -p /app/faiss_index /app/temp \
    && chown -R app:app /app/faiss_index /app/temp
USER app

EXPOSE 8300

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8300", "--no-access-log"]
