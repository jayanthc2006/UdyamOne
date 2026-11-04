"""Quote preview API routes."""

from fastapi import APIRouter, HTTPException, status

from app.models.pricing import QuoteRequest, QuoteResponse
from app.services.pricing_service import PricingValidationError, generate_quote

router = APIRouter(prefix="/quotes", tags=["quotes"])


@router.post("/preview", response_model=QuoteResponse)
def preview_quote(request: QuoteRequest) -> QuoteResponse:
    """Generate a quote only when the selected bundle is eligible."""
    try:
        return generate_quote(request)
    except PricingValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
