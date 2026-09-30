from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import backend.models  # noqa: F401
from backend.core.config import get_settings
from backend.core.exceptions import register_exception_handlers
from backend.ml.artifacts import get_model_artifacts
from backend.modules.admin.router import router as admin_router
from backend.modules.auth.router import router as auth_router
from backend.modules.chat.open_router import router as open_chat_router
from backend.modules.chat.router import router as chat_router
from backend.modules.evaluators.router import router as evaluators_router
from backend.modules.recommendation.router import router as recommendation_router
from backend.modules.students.router import router as students_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    get_model_artifacts()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    for router in (
        auth_router,
        students_router,
        evaluators_router,
        admin_router,
        recommendation_router,
        chat_router,
        open_chat_router,
    ):
        app.include_router(router)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
