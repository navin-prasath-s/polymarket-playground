import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api import user_route

# LOGGING = {
#     "version": 1,
#     "disable_existing_loggers": False,
#     "formatters": {
#         "default": {
#             "fmt": "%(asctime)s %(levelname)-8s %(name)s %(message)s",
#             "datefmt": "%H:%M:%S",
#         },
#     },
#     "handlers": {
#         "console": {
#             "class": "logging.StreamHandler",
#             "formatter": "default",
#         },
#     },
#     "loggers": {
#         # root logger
#         "": {
#             "handlers": ["console"],
#             "level": "INFO",
#         },
#         # optionally adjust uvicorn & sqlalchemy verbosity
#         "uvicorn.error": {
#             "handlers": ["console"],
#             "level": "INFO",
#             "propagate": False,
#         },
#         "uvicorn.access": {
#             "handlers": ["console"],
#             "level": "INFO",
#             "propagate": False,
#         },
#     },
# }
#
# logging.config.dictConfig(LOGGING)

# @asynccontextmanager
# async def lifespan(app):
#     logger.info("Starting up application")
#     yield
#     logger.info("Shutting down application")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# app.include_router(auth.router)
app = FastAPI(debug=True)


@app.get("/")
async def root():
    return {"message": "Server is up and running"}

app.include_router(user_route.router)

# uvicorn src.api.app:app --reload --port 8000