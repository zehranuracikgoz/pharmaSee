import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.models import models  # noqa: F401 — registers tables on Base.metadata
from app.routers import fda, stocks, analysis
from app.services.fda_service import run_scheduled_sync

# uvicorn only configures its own loggers; without this, app INFO logs are dropped
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger ("httpx").setLevel(logging.WARNING)  #one line per request is too noisy
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    scheduler=AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        run_scheduled_sync,
        trigger="cron",
        hour=2,
        minute=0,
        id="daily_fda_sync",
        replace_existing=True,
        coalesce=True, #run once even if several runs were missed
        misfire_grace_time=3600,  #still run if the server was busy/asleep up to 1h past 02:00
    )
    scheduler.start()
    logger.info("Scheduler started — daily FDA sync at 02:00 UTC")
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="PharmaSee API",
    description="Analytics platform for FDA drug approvals and biotech stock performance.",
    version="0.1.0",
    lifespan=lifespan,
)

# cors
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    # Starlette does not support wildcards in allow_origins; regex covers Vercel prod + previews
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# routes
app.include_router(fda.router)
app.include_router(stocks.router)
app.include_router(stocks.companies_router)
app.include_router(analysis.router)


@app.get("/", tags=["Health"])
async def root():
    return {
        "name" : "PharmaSee API",
        "version": "0.1.0",
        "status": "ok",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}
