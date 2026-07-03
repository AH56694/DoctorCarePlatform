# DoctorCarePlatform

DoctorCarePlatform is a monorepo scaffold for an AI medical companion and caregiver matching platform.

## Services

- `frontend`: React + TypeScript console
- `backend`: Main FastAPI business service
- `python-service`: Core AI/RAG service for intelligent consultation, knowledge retrieval, and knowledge-base ingestion
- `infra`: Nginx and PostgreSQL initialization files

## Quick Start

```powershell
docker compose up --build
```

Copy `.env.example` to `.env` only when you need to override demo defaults or provide real API keys.

If Docker Hub cannot be reached while building `python:3.11-slim` or `node:22-alpine`, use the local hybrid launcher. It uses the existing local Python/Node environments and starts only Redis/MinIO through Docker:

```powershell
.\scripts\start-local.ps1
```

Open:

- Frontend: `http://127.0.0.1:5173`
- Backend docs: `http://127.0.0.1:8000/docs`
- RAG docs: `http://127.0.0.1:8300/docs`

Stop local services:

```powershell
.\scripts\stop-local.ps1
```

Manual local development:

```powershell
uvicorn backend.app.main:app --reload --port 8000
cd python-service
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8300
cd frontend
npm install --cache .\.npm-cache
npm --cache .\.npm-cache run dev
npm --cache .\.npm-cache run build
```

## Key API Paths

- `backend`: `GET /health`, `GET /api/v1/dashboard/summary`
- `backend AI gateway`: `POST /api/v1/ai/chat`
- `backend admin knowledge`: `POST /api/v1/admin/knowledge-items`, `DELETE /api/v1/admin/knowledge-items/{id}`
- `python-service`: `POST /api/ask`, `POST /api/v1/knowledge/ingest`, `DELETE /api/v1/knowledge/{doc_id}`

## Production Notes

Before production use, configure:

- DeepSeek or OpenAI-compatible API key
- Aliyun SMS signature, template code, and access keys
- Licensed medical knowledge sources
- Production secret management, audit policy, and model safety evaluation
