import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from src.api import user_route, order_route, position_route, admin_route
from src.background_task import run_market_sync



logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


scheduler = BackgroundScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(run_market_sync, 'interval', minutes=5, max_instances=1, coalesce=True)
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    return {"message": "Server is up and running"}

app.include_router(user_route.router)
app.include_router(order_route.router)
app.include_router(position_route.router)
app.include_router(admin_route.router)

# uvicorn src.api.app:app --reload --port 8000


