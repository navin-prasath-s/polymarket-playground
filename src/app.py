import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api import user_route, order_route, position_route



logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

app = FastAPI(debug=True)


@app.get("/")
async def root():
    return {"message": "Server is up and running"}

app.include_router(user_route.router)
app.include_router(order_route.router)\

app.include_router(position_route.router)

# uvicorn src.api.app:app --reload --port 8000


