from fastapi import APIRouter

from backend.app.api.v1.routes import accounts, admin, chat, conversations, dashboard, jobs, profiles, reviews, sms

api_router = APIRouter()
api_router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
api_router.include_router(reviews.router, prefix="/reviews", tags=["reviews"])
api_router.include_router(chat.router, prefix="/ai", tags=["ai"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
api_router.include_router(sms.router, prefix="/sms", tags=["sms"])
