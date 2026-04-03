import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import ALLOWED_ORIGINS
from backend.db.database import init_db
from backend.routes import wallets, leaderboard, markets, alerts
from backend.services import poller

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    poller.start()
    yield
    poller.stop()


app = FastAPI(title="Polymarket Sharp Tracker", docs_url=None, redoc_url=None, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(alerts.router)
app.include_router(wallets.router)
app.include_router(leaderboard.router)
app.include_router(markets.router)

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
