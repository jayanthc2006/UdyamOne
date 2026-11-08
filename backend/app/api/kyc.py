"""KYC document presence, review, and final-approval routes."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse

from app.models.kyc import (
    KycAdditionalDocumentsRequest,
    KycAssessment,
    KycApplicantProfileRequest,
    KycConsentRequest,
    KycDocumentCorrectionRequest,
    KycDocumentReviewRequest,
    KycDocumentType,
    KycDocumentValidation,
    KycFinalizationResponse,
)
from app.services.applicant_service import ApplicantNotFoundError
from app.models.recommendation import RecommendationRequest
from app.models.verification import RegistryVerificationStatus
from app.services import applicant_service, registry_verification_service
from app.services.kyc_service import (
    KycConsentRequiredError,
    KycConfigurationError,
    KycOcrError,
    KycStateError,
    KycUploadValidationError,
    correct_extracted_fields,
    finalize_applicant,
    get_assessment,
    get_document_file,
    get_registry_verification_context,
    process_document,
    record_consent,
    request_additional_documents,
    review_document,
    save_document,
    set_applicant_profile,
    require_current_consent,
)
from app.services.recommendation_service import generate_recommendations
from app.security.kyc_auth import (
    KycPrincipal,
    get_current_kyc_principal,
    require_applicant_access,
    require_kyc_read_access,
    require_kyc_role,
)

router = APIRouter(prefix="/kyc", tags=["kyc"])
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_UPLOAD_TYPES = {"application/pdf", "image/jpeg", "image/png"}


def _raise_for_state_error(error: KycStateError) -> None:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=str(error),
    ) from error


def _raise_for_configuration_error(error: KycConfigurationError) -> None:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=str(error),
    ) from error


@router.get("/{applicant_id}", response_model=KycAssessment)
def get_kyc_assessment(
    applicant_id: str,
    principal: KycPrincipal = Depends(get_current_kyc_principal),
) -> KycAssessment:
    """Return document presence and review state, without checking registries."""
    require_kyc_read_access(principal, applicant_id)
    try:
        return get_assessment(applicant_id)
    except KycConfigurationError as error:
        _raise_for_configuration_error(error)
    except KycStateError as error:
        _raise_for_state_error(error)
    except registry_verification_service.RegistryPersistenceError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error


@router.post("/{applicant_id}/verify-registries", response_model=KycAssessment)
def verify_kyc_registries(
    applicant_id: str,
    principal: KycPrincipal = Depends(get_current_kyc_principal),
) -> KycAssessment:
    """Compare corrected KYC fields with the synthetic competition registries."""
    require_kyc_role(principal, "CUSTOMER")
    require_applicant_access(principal, applicant_id)
    try:
        require_current_consent(applicant_id)
        business_name, city, document_values, _ = (
            get_registry_verification_context(applicant_id)
        )
        applicant = None
        if applicant_id.startswith("APPL-"):
            try:
                applicant = applicant_service.get_applicant(applicant_id)
            except ApplicantNotFoundError as error:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Applicant was not found.",
                ) from error
            business_name = applicant.profile.business_name
            city = applicant.profile.city

        results = registry_verification_service.verify_applicant_registries(
            applicant_id,
            business_name,
            city,
            document_values,
        )

        if applicant is not None:
            verified_profile = applicant.profile.business_profile.model_copy(
                update={
                    "gstin_verified": (
                        results["GSTIN"].status
                        is RegistryVerificationStatus.VERIFIED
                    )
                }
            )
            recommendations = generate_recommendations(
                RecommendationRequest(
                    business_profile=verified_profile,
                    business_segment=applicant.profile.business_segment,
                    primary_requirements=applicant.profile.primary_requirements,
                )
            )
            if recommendations != applicant.recommendations:
                applicant_service.update_applicant(
                    applicant_id,
                    applicant.profile,
                    recommendations,
                )
        return get_assessment(applicant_id)
    except KycConfigurationError as error:
        _raise_for_configuration_error(error)
    except KycStateError as error:
        _raise_for_state_error(error)
    except KycConsentRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except registry_verification_service.RegistryPersistenceError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error


@router.put(
    "/{applicant_id}/documents/{document_type}",
    response_model=KycAssessment,
)
async def upload_kyc_document(
    applicant_id: str,
    document_type: KycDocumentType,
    request: Request,
    principal: KycPrincipal = Depends(get_current_kyc_principal),
) -> KycAssessment:
    """Validate and store a document locally; no external provider is used."""
    require_kyc_role(principal, "CUSTOMER")
    require_applicant_access(principal, applicant_id)
    content_type = request.headers.get("content-type", "").split(";", maxsplit=1)[0].lower()
    if content_type not in ALLOWED_UPLOAD_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload a PNG, JPEG, or PDF document.",
        )
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="The uploaded document exceeds the 10 MB limit.",
        )
    chunks = bytearray()
    async for chunk in request.stream():
        if len(chunks) + len(chunk) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="The uploaded document exceeds the 10 MB limit.",
            )
        chunks.extend(chunk)
    try:
        return save_document(
            applicant_id,
            document_type,
            bytes(chunks),
            content_type,
        )
    except KycConfigurationError as error:
        _raise_for_configuration_error(error)
    except KycConsentRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except KycStateError as error:
        _raise_for_state_error(error)
    except KycUploadValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error


@router.get("/{applicant_id}/documents/{document_type}/file")
def retrieve_kyc_document(
    applicant_id: str,
    document_type: KycDocumentType,
    principal: KycPrincipal = Depends(get_current_kyc_principal),
) -> FileResponse:
    """Download only the selected applicant's locally stored document."""
    require_kyc_read_access(principal, applicant_id)
    try:
        path, content_type = get_document_file(applicant_id, document_type)
    except KycStateError as error:
        _raise_for_state_error(error)
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested document is not available.",
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    extension = path.suffix
    return FileResponse(
        path,
        media_type=content_type,
        filename=f"{document_type.value}{extension}",
        content_disposition_type="inline",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "Referrer-Policy": "no-referrer",
        },
    )


@router.post(
    "/{applicant_id}/documents/{document_type}/process",
    response_model=KycAssessment,
)
def process_kyc_document(
    applicant_id: str,
    document_type: KycDocumentType,
    principal: KycPrincipal = Depends(get_current_kyc_principal),
) -> KycAssessment:
    """Run local OCR and document-specific extraction."""
    require_kyc_role(principal, "CUSTOMER")
    require_applicant_access(principal, applicant_id)
    try:
        return process_document(applicant_id, document_type)
    except KycConfigurationError as error:
        _raise_for_configuration_error(error)
    except KycStateError as error:
        _raise_for_state_error(error)
    except KycConsentRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except KycOcrError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error


@router.patch(
    "/{applicant_id}/documents/{document_type}/corrections",
    response_model=KycAssessment,
)
def correct_kyc_document_fields(
    applicant_id: str,
    document_type: KycDocumentType,
    request: KycDocumentCorrectionRequest,
    principal: KycPrincipal = Depends(get_current_kyc_principal),
) -> KycAssessment:
    """Persist customer-entered corrections without claiming document verification."""
    require_kyc_role(principal, "CUSTOMER")
    require_applicant_access(principal, applicant_id)
    try:
        return correct_extracted_fields(applicant_id, document_type, request.fields)
    except KycConfigurationError as error:
        _raise_for_configuration_error(error)
    except KycStateError as error:
        _raise_for_state_error(error)
    except KycConsentRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error


@router.put(
    "/{applicant_id}/profile",
    response_model=KycAssessment,
)
def update_kyc_profile(
    applicant_id: str,
    request: KycApplicantProfileRequest,
    principal: KycPrincipal = Depends(get_current_kyc_principal),
) -> KycAssessment:
    """Save optional submitted business details for potential mismatch warnings."""
    require_kyc_role(principal, "CUSTOMER")
    require_applicant_access(principal, applicant_id)
    try:
        require_current_consent(applicant_id)
        return set_applicant_profile(
            applicant_id,
            request.business_name,
            request.business_address,
        )
    except KycConfigurationError as error:
        _raise_for_configuration_error(error)
    except KycStateError as error:
        _raise_for_state_error(error)
    except KycConsentRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error


@router.post(
    "/{applicant_id}/documents/{document_type}/review",
    response_model=KycAssessment,
)
def review_kyc_document(
    applicant_id: str,
    document_type: KycDocumentType,
    request: KycDocumentReviewRequest,
    principal: KycPrincipal = Depends(get_current_kyc_principal),
) -> KycAssessment:
    """Record an explicit manual document review; registry state remains untouched."""
    require_kyc_role(principal, "REVIEWER")
    require_applicant_access(principal, applicant_id)
    try:
        return review_document(
            applicant_id,
            document_type,
            KycDocumentValidation(request.validation),
        )
    except KycConfigurationError as error:
        _raise_for_configuration_error(error)
    except KycStateError as error:
        _raise_for_state_error(error)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error


@router.post(
    "/{applicant_id}/finalize",
    response_model=KycFinalizationResponse,
)
def finalize_kyc(
    applicant_id: str,
    principal: KycPrincipal = Depends(get_current_kyc_principal),
) -> KycFinalizationResponse:
    """Confirm readiness only after configured requirements and corrections pass."""
    require_kyc_role(principal, "REVIEWER")
    require_applicant_access(principal, applicant_id)
    try:
        assessment = finalize_applicant(applicant_id)
    except KycConfigurationError as error:
        _raise_for_configuration_error(error)
    except KycStateError as error:
        _raise_for_state_error(error)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return KycFinalizationResponse(
        message=(
            "Required document checks are complete. The prototype assessment is "
            "ready for an authorized human decision; this is not production approval."
        ),
        assessment=assessment,
    )


@router.post("/{applicant_id}/consent", response_model=KycAssessment)
def set_kyc_consent(
    applicant_id: str,
    request: KycConsentRequest,
    principal: KycPrincipal = Depends(get_current_kyc_principal),
) -> KycAssessment:
    """Persist the customer's affirmative or negative consent decision."""
    require_kyc_role(principal, "CUSTOMER")
    require_applicant_access(principal, applicant_id)
    try:
        return record_consent(applicant_id, request.consented)
    except KycConfigurationError as error:
        _raise_for_configuration_error(error)
    except KycStateError as error:
        _raise_for_state_error(error)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error


@router.post(
    "/{applicant_id}/additional-documents",
    response_model=KycAssessment,
)
def request_kyc_additional_documents(
    applicant_id: str,
    request: KycAdditionalDocumentsRequest,
    principal: KycPrincipal = Depends(get_current_kyc_principal),
) -> KycAssessment:
    """Persist reviewer-requested document types for this applicant."""
    require_kyc_role(principal, "REVIEWER")
    require_applicant_access(principal, applicant_id)
    try:
        return request_additional_documents(applicant_id, request.document_types)
    except KycConfigurationError as error:
        _raise_for_configuration_error(error)
    except KycStateError as error:
        _raise_for_state_error(error)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
