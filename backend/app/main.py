from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import settings
from app.routers.auth import router as auth_router
from app.routers.postings import router as postings_router
from app.routers.submissions import router as submissions_router


app = FastAPI(
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
    return {"status": "ok"}
