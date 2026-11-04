"""Eligibility API routes."""

from fastapi import APIRouter

from app.schemas.catalogue import EligibilityCheckRequest, EligibilityCheckResponse
from app.services.catalogue_loader import load_catalogue
from app.services.eligibility_service import evaluate_bundle_eligibility

router = APIRouter(prefix="/eligibility", tags=["eligibility"])


@router.post("/check", response_model=EligibilityCheckResponse)
def check_eligibility(request: EligibilityCheckRequest) -> EligibilityCheckResponse:
    """Evaluate selected products with the existing bundle eligibility service."""
    results = evaluate_bundle_eligibility(
        request.selected_product_ids,
        load_catalogue(),
        request.business_profile,
    )
    return EligibilityCheckResponse(results=results)
