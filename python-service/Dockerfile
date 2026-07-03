FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app

COPY python-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY python-service/ ./

EXPOSE 8300

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8300"]
