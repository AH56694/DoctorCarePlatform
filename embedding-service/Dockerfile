FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY embedding_service ./embedding_service

CMD ["uvicorn", "embedding_service.app.main:app", "--host", "0.0.0.0", "--port", "8200"]
