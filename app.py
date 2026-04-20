from __future__ import annotations

from contextlib import asynccontextmanager
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from graph_of_god_backend.api.routers import api_router
from graph_of_god_backend.container import AppContainer, build_container


def create_app(*, container: AppContainer | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        resolved_container = container or build_container()
        app.state.container = resolved_container
        try:
            yield
        finally:
            resolved_container.shutdown()

    app = FastAPI(
        title="GraphOfGod Backend",
        summary="Backend для фонового сбора связей VK.",
        description=(
            "Сервис принимает VK-профиль, запускает фоновую задачу на сбор друзей "
            "или подписчиков и отдает статус задачи через polling endpoint."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    return app
