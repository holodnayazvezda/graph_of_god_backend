from __future__ import annotations

from fastapi import APIRouter

from graph_of_god_backend.api.schemas.friend_links import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Проверка доступности backend")
async def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok")
