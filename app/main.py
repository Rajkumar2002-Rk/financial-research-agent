from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from fastapi import FastAPI
from contextlib import asynccontextmanager
import redis.asyncio as aioredis

from app.utils.config import get_settings
from app.utils.logger import setup_logging, get_logger
from app.api.middleware import setup_middleware
from app.api.routes import health, analysis

logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("server_starting")

    redis_client = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    try:
        await redis_client.ping()
        logger.info("redis_connected")
    except Exception as e:
        logger.error("redis_failed", error=str(e))

    app.state.redis = redis_client
    yield

    await redis_client.aclose()
    logger.info("server_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Financial Research Agent",
        version="1.0.0",
        lifespan=lifespan,
    )

    setup_middleware(app)
    app.include_router(health.router)
    app.include_router(analysis.router)

    frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
    if os.path.exists(frontend_path):
        app.mount("/static", StaticFiles(directory=frontend_path), name="static")

        @app.get("/", include_in_schema=False)
        async def serve_frontend():
            return FileResponse(os.path.join(frontend_path, "index.html"))
    return app


app = create_app()