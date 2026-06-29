# DoctorCarePlatform

DoctorCarePlatform is a monorepo scaffold for an AI medical companion and caregiver matching platform.

## Services

- `frontend`: React + TypeScript console
- `backend`: Main FastAPI business service
- `ai-service`: AI consultation orchestration service with two-level intent classification, RAG routing, and cache boundaries
- `embedding-service`: Independent embedding API with BGE-compatible interface and deterministic local fallback
- `infra`: Nginx and PostgreSQL initialization files

## Quick Start

```powershell
docker compose up --build
```

Copy `.env.example` to `.env` only when you need to override demo defaults or provide real API keys.

Local development:

```powershell
uvicorn backend.app.main:app --reload --port 8000
uvicorn ai_service.app.main:app --reload --port 8100
uvicorn embedding_service.app.main:app --reload --port 8200
cd frontend
npm install --cache .\.npm-cache
npm --cache .\.npm-cache run dev
npm --cache .\.npm-cache run build
```

## Key API Paths

- `backend`: `GET /health`, `GET /api/v1/dashboard/summary`
- `ai-service`: `POST /api/v1/chat`, `POST /api/v1/intents/classify`
- `embedding-service`: `POST /api/v1/embeddings`

## Production Notes

Before production use, configure:

- DeepSeek or OpenAI-compatible API key
- Aliyun SMS signature, template code, and access keys
- Licensed medical knowledge sources
- Production secret management, audit policy, and model safety evaluation
