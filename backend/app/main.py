import json
import logging
import os
import socket
import sys
from time import perf_counter
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine, settings
from app.routers.auth import router as auth_router
from app.routers.postings import router as postings_router
from app.routers.submissions import router as submissions_router


access_logger = logging.getLogger("resume_ip.access")
if not any(getattr(handler, "_resume_ip_access", False) for handler in access_logger.handlers):
    access_handler = logging.StreamHandler(sys.stdout)
    access_handler.setFormatter(logging.Formatter("%(message)s"))
    access_handler._resume_ip_access = True  # type: ignore[attr-defined]
    access_logger.addHandler(access_handler)
access_logger.propagate = False
access_logger.setLevel(logging.INFO)


def instance_name() -> str:
    return os.getenv("INSTANCE_NAME") or socket.gethostname()


class RequestInstrumentationMiddleware:
    """Add instance metadata and one sanitized access record to HTTP responses."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started_at = perf_counter()
        served_by = instance_name()
        status_code: int | None = None

        async def instrumented_send(message):
            nonlocal status_code

            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-served-by", served_by.encode("latin-1", "replace")))
                message["headers"] = headers

            await send(message)

        try:
            await self.app(scope, receive, instrumented_send)
        finally:
            access_logger.info(
                json.dumps(
                    {
                        "instance": served_by,
                        "method": scope["method"],
                        "path": scope["path"],
                        "status": status_code if status_code is not None else 500,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 3),
                    },
                    separators=(",", ":"),
                )
            )


class InstrumentedFastAPI(FastAPI):
    """Keep FastAPI's public API while wrapping its completed middleware stack."""

    def build_middleware_stack(self):
        return RequestInstrumentationMiddleware(super().build_middleware_stack())


app = InstrumentedFastAPI(
    title="Resume Intelligence Portal",
)


def configured_cors_origins(value: str) -> list[str]:
    origins = [origin.strip().removesuffix("/") for origin in value.split(",")]
    origins = [origin for origin in origins if origin]

    for origin in origins:
        parsed = urlsplit(origin)

        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path
        ):
            raise ValueError("CORS_ALLOWED_ORIGINS must contain exact HTTP(S) origins")

    return origins


cors_origins = configured_cors_origins(settings.cors_allowed_origins)

if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )


app.include_router(auth_router)
app.include_router(postings_router)
app.include_router(submissions_router)


@app.get("/health")
def health_check():
    return {"status": "ok", "instance": instance_name()}


@app.get("/health/db")
def database_health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "instance": instance_name(),
                "db": "unavailable",
            },
        )

    return {"status": "ok", "instance": instance_name(), "db": "ok"}
