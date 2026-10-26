"""FastAPI entry point. Run: uvicorn app.main:app --reload (from backend/)."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import create_all
from app.routes import audit, auth, dashboard, users

DISCLAIMER = "Hackathon prototype. Not an official AICTE system. Decision support only."


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_all()
    yield


app = FastAPI(title=settings.app_name, description=DISCLAIMER, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (auth, users, audit, dashboard):
    app.include_router(module.router)


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "disclaimer": DISCLAIMER}
