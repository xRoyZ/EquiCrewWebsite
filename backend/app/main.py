"""FastAPI application of the EquiCrew contact API.

Start:  uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log
(from backend/; --no-access-log keeps visitor IP addresses out of the logs).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app import contact
from app.body_limit import BodySizeLimitMiddleware
from app.config import get_settings

logger = logging.getLogger("equicrew.api")

VALIDATION_DETAIL = "Invalid input."
INTERNAL_ERROR_DETAIL = "Internal server error."


def _internal_error(request_method: str, path: str, exc: BaseException) -> JSONResponse:
    """Log an unexpected error without its message and answer a generic 500.

    Only the exception type is logged: an exception's text can carry SMTP details,
    credentials or visitor data, none of which may reach a log or a response.
    """
    logger.error("unhandled %s on %s %s", type(exc).__name__, request_method, path)
    return JSONResponse(status_code=500, content={"detail": INTERNAL_ERROR_DETAIL})


class CatchAllErrorsMiddleware:
    """Turn any unhandled exception into a generic 500 {"detail": str}.

    Registered inside the CORS middleware, so the 500 still carries the CORS headers
    (Starlette's own Exception handler runs outside of every user middleware).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        response_started = False

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception as exc:
            if response_started:
                raise
            response = _internal_error(scope.get("method", "?"), scope.get("path", "?"), exc)
            await response(scope, receive, send)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Validate the whole configuration once at startup, so a malformed value refuses
    # to start and names the variable instead of failing the first request.
    get_settings()
    yield


settings = get_settings()

app = FastAPI(title="EquiCrew Contact API", lifespan=lifespan)

# Order matters: the middleware added last is the outermost one.
app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
app.add_middleware(CatchAllErrorsMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": str(exc.detail)},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, _exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": VALIDATION_DETAIL})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return _internal_error(request.method, request.url.path, exc)


@app.get("/api/health")
async def health() -> dict[str, str]:
    # Reads the same settings object the contact route uses.
    get_settings()
    return {"status": "ok"}


app.include_router(contact.router)
