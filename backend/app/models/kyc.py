"""KYC document workflow schemas for the Phase 3.1 prototype."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.verification import (
    RegistryVerificationResult,
    RegistryVerificationStatus,
)


class KycDocumentType(str, Enum):
    GST_CERTIFICATE = "gst_certificate"
    UDYAM_CERTIFICATE = "udyam_certificate"
    SIGNATORY_ID = "signatory_id"
    ADDRESS_PROOF = "address_proof"

    @property
    def display_name(self) -> str:
        return {
            KycDocumentType.GST_CERTIFICATE: "GST certificate",
            KycDocumentType.UDYAM_CERTIFICATE: "Udyam certificate",
            KycDocumentType.SIGNATORY_ID: "Signatory ID",
            KycDocumentType.ADDRESS_PROOF: "Address proof",
        }[self]


class KycDocumentPresence(str, Enum):
    NOT_PROVIDED = "NOT_PROVIDED"
    PROVIDED = "PROVIDED"


class KycDocumentValidation(str, Enum):
    NOT_REVIEWED = "NOT_REVIEWED"
    VALID = "VALID"
    INVALID = "INVALID"


class KycProcessingStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    UNREADABLE = "UNREADABLE"
    FAILED = "FAILED"


class KycFieldStatus(str, Enum):
    EXTRACTED = "EXTRACTED"
    MISSING = "MISSING"
    INVALID_FORMAT = "INVALID_FORMAT"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    MANUALLY_CORRECTED = "MANUALLY_CORRECTED"


class KycRecencyStatus(str, Enum):
    VALID = "VALID"
    EXPIRED = "EXPIRED"
    INCONCLUSIVE = "INCONCLUSIVE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class KycExtractedField(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    label: str
    value: str | None = None
    original_value: str | None = None
    corrected_value: str | None = None
    correction_applied: bool = False
    confidence: float | None = Field(default=None, ge=0, le=1)
    status: KycFieldStatus
    flags: list[str] = Field(default_factory=list)


class KycExtraction(BaseModel):
    model_config = ConfigDict(frozen=True)

    processing_status: KycProcessingStatus = KycProcessingStatus.NOT_STARTED
    detected_document_type: KycDocumentType | None = None
    classification_matches_category: bool | None = None
    fields: list[KycExtractedField] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    invalid_fields: list[str] = Field(default_factory=list)
    low_confidence_fields: list[str] = Field(default_factory=list)
    mismatch_warnings: list[str] = Field(default_factory=list)
    confidence_available: bool = False
    error_code: str | None = None
    address_proof_recency: KycRecencyStatus | None = None
    address_proof_reference_date: str | None = None


class KycDocumentState(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_type: KycDocumentType
    display_name: str
    presence: KycDocumentPresence
    validation: KycDocumentValidation
    registry_verification: RegistryVerificationStatus | Literal["NOT_CHECKED"] = (
        "NOT_CHECKED"
    )
    document_source: Literal[
        "NOT_PROVIDED", "COMPETITION_SAMPLE", "CUSTOMER_UPLOAD"
    ] = "NOT_PROVIDED"
    recency_status: KycRecencyStatus = KycRecencyStatus.NOT_APPLICABLE
    upload_status: Literal["NOT_UPLOADED", "UPLOADED"] = "NOT_UPLOADED"
    processing_status: KycProcessingStatus = KycProcessingStatus.NOT_STARTED
    original_filename: str | None = None
    file_size_bytes: int | None = None
    content_type: str | None = None
    extraction: KycExtraction | None = None


class KycConsentState(BaseModel):
    model_config = ConfigDict(frozen=True)

    applicant_id: str
    consented: bool
    consent_version: str
    timestamp: str


class KycAssessment(BaseModel):
    model_config = ConfigDict(frozen=True)

    applicant_id: str
    documents: list[KycDocumentState]
    required_documents: list[KycDocumentType]
    requested_documents: list[KycDocumentType] = Field(default_factory=list)
    upload_requests: list[KycDocumentType]
    next_steps: list[str]
    ready_for_approval: bool
    consent: KycConsentState | None = None
    gstin_verification: RegistryVerificationResult | None = None
    udyam_verification: RegistryVerificationResult | None = None
    required_registry_verifications: list[Literal["GSTIN", "UDYAM"]] = Field(
        default_factory=list
    )


class KycConsentRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    consented: bool


class KycAdditionalDocumentsRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_types: list[KycDocumentType] = Field(min_length=1, max_length=4)

    @field_validator("document_types")
    @classmethod
    def document_types_must_be_unique(
        cls, document_types: list[KycDocumentType]
    ) -> list[KycDocumentType]:
        if len(document_types) != len(set(document_types)):
            raise ValueError("document_types must not contain duplicates.")
        return document_types


class KycDocumentReviewRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    validation: Literal["VALID", "INVALID"]


class KycDocumentCorrectionRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    fields: dict[str, str | None] = Field(min_length=1, max_length=20)


class KycApplicantProfileRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    business_name: str | None = Field(default=None, max_length=200)
    business_address: str | None = Field(default=None, max_length=500)


class KycFinalizationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    finalized: Literal[True] = True
    message: str
    assessment: KycAssessment | None = None
