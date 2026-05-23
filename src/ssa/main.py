from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.ssa.api.router import api_router
from src.ssa.config import settings
from src.ssa.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.include_router(api_router)
    return app


app = create_app()
