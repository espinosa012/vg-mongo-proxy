from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from vg_mongo_proxy.config import get_settings
from vg_mongo_proxy.db import close_db, init_db, ping_database
from vg_mongo_proxy.routes import actions, files


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager to initialize and clean up database connections."""
    settings = get_settings()
    try:
        await init_db(settings.mongodb_uri)
    except Exception as exc:
        print(f"[vg-mongo-proxy] Warning: Database connection initialization deferred: {exc}")
    yield
    await close_db()


def create_app() -> FastAPI:
    """Create and configure FastAPI application instance."""
    settings = get_settings()

    app = FastAPI(
        title="vg-mongo-proxy",
        description="MongoDB HTTP Proxy with Data API and GridFS storage",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", tags=["System"])
    async def root():
        """Root endpoint returning API status and docs link."""
        return {
            "service": "vg-mongo-proxy",
            "status": "online",
            "docs_url": "/docs",
        }

    @app.get("/health", tags=["System"])
    async def health():
        """Health check endpoint to wake up Render instance and verify MongoDB connectivity."""
        ping_result = await ping_database()
        if ping_result.get("connected"):
            return {
                "status": "healthy",
                "database": "connected",
                "latency_ms": ping_result.get("latency_ms"),
            }
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "error": ping_result.get("error"),
            },
        )

    # Register routers
    app.include_router(actions.router)
    app.include_router(files.router)

    return app


app = create_app()
