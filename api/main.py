"""
FastAPI Application Entry Point

Main application factory with:
- Middleware configuration (CORS, JWT auth stub)
- Lifespan handlers (database connections)
- Health check endpoint
- Request/response logging
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

import motor.motor_asyncio
import redis.asyncio as redis
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from .schemas import HealthResponse

logger = logging.getLogger(__name__)


class AppState:
    """Global application state."""

    postgres_engine = None
    redis_client = None
    mongodb_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for startup/shutdown.

    Initializes database connections on startup and closes on shutdown.
    """
    logger.info("Starting Axiom Credit API")

    # ===== STARTUP =====
    try:
        # PostgreSQL
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            # Convert postgresql:// to postgresql+asyncpg://
            if db_url.startswith("postgresql://"):
                db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
            AppState.postgres_engine = create_async_engine(
                db_url,
                echo=os.getenv("DEBUG", "False").lower() == "true",
                pool_size=20,
                max_overflow=40,
            )
            logger.info("Connected to PostgreSQL")

        # MongoDB
        mongo_url = os.getenv("MONGODB_URL")
        if mongo_url:
            AppState.mongodb_client = motor.motor_asyncio.AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=2000)
            await AppState.mongodb_client.admin.command("ping")
            logger.info("Connected to MongoDB")

        # Redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        AppState.redis_client = await redis.from_url(redis_url, socket_timeout=2)
        await AppState.redis_client.ping()
        logger.info("Connected to Redis")

        logger.info("Axiom Credit API started successfully")

    except Exception as e:
        logger.error(f"Error during startup (Degraded Mode): {e}")
        # We don't raise here so the API can still serve health/score with mocks if needed

    yield

    # ===== SHUTDOWN =====
    logger.info("Shutting down Axiom Credit API")

    if AppState.postgres_engine:
        await AppState.postgres_engine.dispose()
        logger.info("Closed PostgreSQL connection")

    if AppState.mongodb_client:
        AppState.mongodb_client.close()
        logger.info("Closed MongoDB connection")

    if AppState.redis_client:
        await AppState.redis_client.close()
        logger.info("Closed Redis connection")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Returns:
        Configured FastAPI instance
    """
    # Create app with lifespan
    app = FastAPI(
        title="Axiom Credit Platform",
        description="Production-grade credit scoring for thin-file users in India",
        version="1.0.0",
        lifespan=lifespan,
    )

    # ===== MIDDLEWARE =====

    # CORS middleware
    allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Request ID middleware for tracking
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(datetime.utcnow().timestamp()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        logger.info(f"{request.method} {request.url.path}")
        response = await call_next(request)
        logger.info(f"{request.method} {request.url.path} - {response.status_code}")
        return response

    # ===== ROUTES =====

    # Health check endpoint
    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        """
        Check API and dependency health.

        Returns:
            HealthResponse with status of all components
        """
        components = {
            "api": "ok",
            "postgres": "ok",
            "mongodb": "ok",
            "redis": "ok",
        }

        # Check PostgreSQL
        if AppState.postgres_engine:
            try:
                import asyncio
                async with AppState.postgres_engine.connect() as conn:
                    await asyncio.wait_for(conn.execute("SELECT 1"), timeout=1.0)
            except Exception as e:
                logger.warning(f"PostgreSQL health check failed: {e}")
                components["postgres"] = "degraded"
        else:
            components["postgres"] = "not_configured"

        # Check MongoDB
        if AppState.mongodb_client:
            try:
                import asyncio
                await asyncio.wait_for(AppState.mongodb_client.admin.command("ping"), timeout=1.0)
            except Exception as e:
                logger.warning(f"MongoDB health check failed: {e}")
                components["mongodb"] = "degraded"
        else:
            components["mongodb"] = "not_configured"

        # Check Redis
        if AppState.redis_client:
            try:
                import asyncio
                await asyncio.wait_for(AppState.redis_client.ping(), timeout=1.0)
            except Exception as e:
                logger.warning(f"Redis health check failed: {e}")
                components["redis"] = "degraded"
        else:
            components["redis"] = "not_configured"

        # Determine overall status
        status_value = (
            "healthy" if all(v == "ok" for v in components.values()) else "degraded"
        )

        return HealthResponse(
            status=status_value,
            timestamp=datetime.utcnow(),
            components=components,
        )

    # ===== IMPORT ROUTES =====
    from .routes import score, verify, evaluate, student

    app.include_router(score.router, prefix="/v1", tags=["scoring"])
    app.include_router(verify.router, prefix="/v1/verify", tags=["verification"])
    app.include_router(evaluate.router, prefix="/evaluate", tags=["evaluation"])
    app.include_router(student.router, prefix="/verify/student", tags=["student_verification"])

    logger.info("FastAPI application created successfully")

    return app


# Create app instance
app = create_app()


# Entry point for uvicorn
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=os.getenv("DEBUG", "False").lower() == "true",
    )
