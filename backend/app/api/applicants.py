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
from app.services import registry_verification_service
from app.services.kyc_service import (
    KycStateError,
    get_registry_verification_context,
    set_applicant_profile,
)
from app.services.pricing_service import PricingValidationError, generate_quote
from app.services.recommendation_service import generate_recommendations

router = APIRouter(prefix="/applicants", tags=["applicants"])


def _verified_gstin_for_profile(
    applicant_id: str,
    business_name: str,
    city: str,
) -> bool:
    _, _, document_values, _ = get_registry_verification_context(applicant_id)
    verifications = registry_verification_service.get_persisted_verifications(
        applicant_id,
        business_name,
        city,
        document_values,
    )
    result = verifications["GSTIN"]
    return result is not None and result.status.value == "VERIFIED"


def _recommendations_for_profile(
    profile: ApplicantProfile,
    gstin_registry_verified: bool,
):
    recommendation_request = RecommendationRequest(
        business_profile=profile.business_profile.model_copy(
            update={"gstin_verified": gstin_registry_verified}
        ),
        business_segment=profile.business_segment,
        primary_requirements=profile.primary_requirements,
    )
    return generate_recommendations(recommendation_request)


def _refresh_registry_eligibility(
    applicant: ApplicantRecord,
    gstin_registry_verified: bool | None = None,
) -> ApplicantRecord:
    if gstin_registry_verified is None:
        gstin_registry_verified = _verified_gstin_for_profile(
            applicant.applicant_id,
            applicant.profile.business_name,
            applicant.profile.city,
        )
    recommendations = _recommendations_for_profile(
        applicant.profile, gstin_registry_verified
    )
    if recommendations != applicant.recommendations:
        return update_applicant(
            applicant.applicant_id,
            applicant.profile,
            recommendations,
        )
    return applicant


def _not_found(error: ApplicantNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.post("", response_model=ApplicantJourneyResponse, status_code=status.HTTP_201_CREATED)
def begin_applicant_journey(request: ApplicantProfile) -> ApplicantJourneyResponse:
    """Create an applicant identity and initial deterministic recommendation set."""
    recommendations = _recommendations_for_profile(request, False)
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
    try:
        get_applicant(applicant_id)
        gstin_verified = _verified_gstin_for_profile(
            applicant_id,
            request.business_name,
            request.city,
        )
        recommendations = _recommendations_for_profile(request, gstin_verified)
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
        applicant = get_applicant(applicant_id)
        return _refresh_registry_eligibility(applicant)
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
        gstin_registry_verified = _verified_gstin_for_profile(
            applicant.applicant_id,
            applicant.profile.business_name,
            applicant.profile.city,
        )
        applicant = _refresh_registry_eligibility(
            applicant, gstin_registry_verified
        )
    except ApplicantNotFoundError as error:
        raise _not_found(error) from error

    try:
        quote = generate_quote(
            QuoteRequest(
                business_profile=applicant.profile.business_profile.model_copy(
                    update={"gstin_verified": gstin_registry_verified}
                ),
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
