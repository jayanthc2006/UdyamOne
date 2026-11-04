"""Top-level API router."""

from fastapi import APIRouter

from app.api.eligibility import router as eligibility_router
from app.api.products import router as products_router
from app.api.quotes import router as quotes_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(products_router)
api_router.include_router(eligibility_router)
api_router.include_router(quotes_router)
