"""Catalogue recommendation API route."""

from fastapi import APIRouter

from app.models.recommendation import RecommendationRequest, RecommendationResponse
from app.services.recommendation_service import generate_recommendations

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post("", response_model=RecommendationResponse)
def get_recommendations(request: RecommendationRequest) -> RecommendationResponse:
    """Return deterministic, quoteable bundles for the submitted business profile."""
    server_checked_request = request.model_copy(
        update={
            "business_profile": request.business_profile.model_copy(
                update={"gstin_verified": False}
            )
        }
    )
    return generate_recommendations(server_checked_request)
