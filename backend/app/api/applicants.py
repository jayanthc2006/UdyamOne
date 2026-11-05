"""Applicant-scoped onboarding, recommendation, and quote routes."""

from fastapi import APIRouter, HTTPException, status

from app.models.applicant import (
    ApplicantJourneyResponse,
    ApplicantProfile,
    ApplicantQuotePreviewRequest,
    ApplicantQuotePreviewResponse,
    ApplicantRecord,
)
from app.models.pricing import QuoteRequest
from app.models.recommendation import RecommendationRequest
from app.services.applicant_service import (
    ApplicantNotFoundError,
    create_applicant,
    get_applicant,
    save_quote_preview,
    update_applicant,
)
from app.services.kyc_service import KycStateError, set_applicant_profile
from app.services.pricing_service import PricingValidationError, generate_quote
from app.services.recommendation_service import generate_recommendations

router = APIRouter(prefix="/applicants", tags=["applicants"])


def _not_found(error: ApplicantNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.post("", response_model=ApplicantJourneyResponse, status_code=status.HTTP_201_CREATED)
def begin_applicant_journey(request: ApplicantProfile) -> ApplicantJourneyResponse:
    """Create an applicant identity and initial deterministic recommendation set."""
    recommendation_request = RecommendationRequest(
        business_profile=request.business_profile,
        business_segment=request.business_segment,
        primary_requirements=request.primary_requirements,
    )
    recommendations = generate_recommendations(recommendation_request)
    applicant = create_applicant(request, recommendations)
    try:
        # This seeds a separate empty KYC manifest for the generated ID. K05 is
        # never referenced here and remains an explicit competition sample only.
        set_applicant_profile(applicant.applicant_id, request.business_name, request.city)
    except KycStateError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The applicant profile was created, but its KYC checklist could not be initialized.",
        ) from error
    return ApplicantJourneyResponse(applicant=applicant, recommendations=recommendations)


@router.put("/{applicant_id}", response_model=ApplicantJourneyResponse)
def update_applicant_journey(
    applicant_id: str,
    request: ApplicantProfile,
) -> ApplicantJourneyResponse:
    """Update profile and recommendations while retaining the applicant identity."""
    recommendation_request = RecommendationRequest(
        business_profile=request.business_profile,
        business_segment=request.business_segment,
        primary_requirements=request.primary_requirements,
    )
    recommendations = generate_recommendations(recommendation_request)
    try:
        applicant = update_applicant(applicant_id, request, recommendations)
    except ApplicantNotFoundError as error:
        raise _not_found(error) from error

    try:
        set_applicant_profile(applicant.applicant_id, request.business_name, request.city)
    except KycStateError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The applicant was updated, but its KYC checklist could not be synchronized.",
        ) from error
    return ApplicantJourneyResponse(applicant=applicant, recommendations=recommendations)


@router.get("/{applicant_id}", response_model=ApplicantRecord)
def get_saved_applicant(applicant_id: str) -> ApplicantRecord:
    """Reload the durable profile and recommendations for a browser refresh."""
    try:
        return get_applicant(applicant_id)
    except ApplicantNotFoundError as error:
        raise _not_found(error) from error


@router.post(
    "/{applicant_id}/quotes/preview",
    response_model=ApplicantQuotePreviewResponse,
)
def preview_applicant_quote(
    applicant_id: str,
    request: ApplicantQuotePreviewRequest,
) -> ApplicantQuotePreviewResponse:
    """Quote selections using the saved profile and existing pricing engine."""
    try:
        applicant = get_applicant(applicant_id)
    except ApplicantNotFoundError as error:
        raise _not_found(error) from error

    try:
        quote = generate_quote(
            QuoteRequest(
                business_profile=applicant.profile.business_profile,
                selected_products=request.selected_products,
            )
        )
    except PricingValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    save_quote_preview(applicant.applicant_id, quote)
    return ApplicantQuotePreviewResponse(applicant_id=applicant.applicant_id, quote=quote)
