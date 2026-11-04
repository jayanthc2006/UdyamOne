"""Application health-check route."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Return the application availability status."""
    return {"status": "ok"}
