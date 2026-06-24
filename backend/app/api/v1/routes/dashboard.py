from fastapi import APIRouter

router = APIRouter()


@router.get("/summary")
async def summary() -> dict:
    return {
        "users": 0,
        "active_jobs": 0,
        "ai_sessions": 0,
        "verification_queue": 0,
        "signals": [
            {"label": "AI问诊", "status": "ready"},
            {"label": "招聘对接", "status": "scaffolded"},
            {"label": "短信通知", "status": "dry-run"},
        ],
    }
