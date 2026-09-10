from fastapi import FastAPI

from app.routers.auth import router as auth_router
from app.routers.postings import router as postings_router
from app.routers.submissions import router as submissions_router


app = FastAPI(
    title="Resume Intelligence Portal",
)


app.include_router(auth_router)
app.include_router(postings_router)
app.include_router(submissions_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
