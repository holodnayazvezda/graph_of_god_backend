from fastapi import APIRouter

from graph_of_god_backend.api.routers.deep_friend_analysis_jobs import (
    router as deep_friend_analysis_jobs_router,
)
from graph_of_god_backend.api.routers.friend_links_jobs import router as friend_links_jobs_router
from graph_of_god_backend.api.routers.health import router as health_router
from graph_of_god_backend.api.routers.social_graph_jobs import router as social_graph_jobs_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(friend_links_jobs_router)
api_router.include_router(social_graph_jobs_router)
api_router.include_router(deep_friend_analysis_jobs_router)

__all__ = ["api_router"]
