"""Catalogue recommendation API route."""

from fastapi import APIRouter

from app.models.recommendation import RecommendationRequest, RecommendationResponse
from app.services.recommendation_service import generate_recommendations

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post("", response_model=RecommendationResponse)
def get_recommendations(request: RecommendationRequest) -> RecommendationResponse:
    """Return deterministic, quoteable bundles for the submitted business profile."""
    return generate_recommendations(request)
