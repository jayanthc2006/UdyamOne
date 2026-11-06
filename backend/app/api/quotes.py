"""Quote preview API routes."""

from fastapi import APIRouter, HTTPException, status

from app.models.pricing import QuoteRequest, QuoteResponse
from app.services.pricing_service import PricingValidationError, generate_quote

router = APIRouter(prefix="/quotes", tags=["quotes"])


@router.post("/preview", response_model=QuoteResponse)
def preview_quote(request: QuoteRequest) -> QuoteResponse:
    """Generate a quote only when the selected bundle is eligible."""
    try:
        server_checked_request = request.model_copy(
            update={
                "business_profile": request.business_profile.model_copy(
                    update={"gstin_verified": False}
                )
            }
        )
        return generate_quote(server_checked_request)
    except PricingValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
