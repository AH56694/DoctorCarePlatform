import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from middleware.middlewares import TimingMiddleware

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

import tools  # noqa: E402,F401  # Registers agent tools on startup.
from api.agent_routes import router as agent_router  # noqa: E402
from api.integration_routes import router as integration_router  # noqa: E402
from api.routes import router  # noqa: E402


def _cors_origins() -> list[str]:
    configured = os.getenv("CORS_ORIGINS")
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


app = FastAPI(title="DoctorCarePlatform Python AI Service", version="0.1.0")
app.add_middleware(TimingMiddleware, enable=True, threshold=0.0)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(integration_router, prefix="/api/v1")


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "DoctorCarePlatform Python AI service is running"}


@app.get("/health")
async def health_check() -> dict[str, object]:
    use_milvus = os.getenv("USE_MILVUS", "false").lower() == "true"
    persist_dir = os.getenv("VECTOR_STORE_PERSIST_DIR", str(Path.cwd() / "faiss_index"))
    vector_store_info: dict[str, object]
    if use_milvus:
        vector_store_info = {
            "type": "Milvus",
            "host": os.getenv("MILVUS_HOST", "localhost"),
            "port": os.getenv("MILVUS_PORT", "19530"),
            "status": "configured",
        }
    else:
        vector_store_info = {
            "type": "FAISS",
            "exists": Path(persist_dir).exists(),
            "directory": persist_dir,
        }

    return {
        "status": "healthy",
        "service": "python-service",
        "environment": {
            "has_dashscope_api_key": bool(os.getenv("DASHSCOPE_API_KEY")),
            "llm_fallback_providers": os.getenv("LLM_FALLBACK_PROVIDERS", "ollama,openai_compatible,retrieval"),
            "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            "ollama_model": os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b"),
            "has_openai_compatible_config": bool(
                os.getenv("OPENAI_COMPATIBLE_BASE_URL") and os.getenv("OPENAI_COMPATIBLE_MODEL")
            ),
            "use_milvus": use_milvus,
            "embedding_model": os.getenv("EMBEDDING_MODEL", "local"),
        },
        "vector_store": vector_store_info,
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=os.getenv("API_HOST", "127.0.0.1"),
        port=int(os.getenv("API_PORT", "8300")),
        reload=True,
    )
