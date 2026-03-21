import time
import uuid
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.utils.logger import get_logger

logger = get_logger(__name__)


def setup_middleware(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)


class RequestLoggingMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        start_time = time.time()

        logger.info(
            "request_started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        response = await call_next(request)

        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.info(
            "request_completed",
            request_id=request_id,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        response.headers["X-Request-ID"] = request_id
        return response