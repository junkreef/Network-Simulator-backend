"""Main FastAPI application entrypoint.

Configures CORS middleware, registers router endpoints, and registers lifespan
event handlers for topology cleanup on application shutdown.
"""

from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import endpoints, websocket
from app.core.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Handles startup and shutdown lifespan events of the FastAPI application.

    Ensures that any running topology is cleanly destroyed on application shutdown.
    """
    # Startup
    yield
    # Shutdown
    try:
        orchestrator = Orchestrator()
        orchestrator.destroy_topology()
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error during topology cleanup on shutdown: %s", e)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS middleware configuration to allow all origins during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(endpoints.router, prefix=settings.API_V1_STR)
app.include_router(websocket.router, prefix=settings.API_V1_STR)

@app.get("/")
def read_root():
    """Root health check endpoint."""
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "version": "1.0.0"
    }
