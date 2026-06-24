from fastapi import APIRouter

from backend.app.api.v1.routes import chat, dashboard, jobs, sms

api_router = APIRouter()
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(chat.router, prefix="/ai", tags=["ai"])
api_router.include_router(sms.router, prefix="/sms", tags=["sms"])
