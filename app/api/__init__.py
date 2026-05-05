"""API routers package."""
from app.api.datasets import router as datasets_router
from app.api.tiles import router as tiles_router
from app.api.health import router as health_router
from app.api.auth import router as auth_router

__all__ = ["datasets_router", "tiles_router", "health_router", "auth_router"]
