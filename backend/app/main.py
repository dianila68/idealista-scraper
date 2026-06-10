from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.core.database import engine
from app.services.scheduler import start_scheduler, stop_scheduler

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    start_scheduler(session_factory)
    log.info("startup", env=settings.log_level)
    yield
    stop_scheduler()
    log.info("shutdown")


app = FastAPI(
    title="idealista-scraper",
    version="0.1.0",
    description="Italian real estate aggregator backend",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.v1 import router as v1_router  # noqa: E402

app.include_router(v1_router, prefix="/api/v1")


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok", "version": app.version}
