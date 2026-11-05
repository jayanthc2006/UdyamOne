"""Top-level API router."""

from fastapi import APIRouter

from app.api.advisor import router as advisor_router
from app.api.applicants import router as applicants_router
from app.api.eligibility import router as eligibility_router
from app.api.kyc_auth import router as kyc_auth_router
from app.api.kyc import router as kyc_router
from app.api.products import router as products_router
from app.api.quotes import router as quotes_router
from app.api.recommendations import router as recommendations_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(advisor_router)
api_router.include_router(applicants_router)
api_router.include_router(kyc_auth_router)
api_router.include_router(products_router)
api_router.include_router(eligibility_router)
api_router.include_router(kyc_router)
api_router.include_router(quotes_router)
api_router.include_router(recommendations_router)
