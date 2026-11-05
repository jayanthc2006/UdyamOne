"""Persistent applicant and journey contracts.

These models add customer-journey context around the existing deterministic
recommendation and quotation contracts. They deliberately do not change the
eligibility, recommendation, or pricing request models.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.business_profile import BusinessProfile
from app.models.pricing import ProductSelection, QuoteResponse
from app.models.recommendation import (
    BusinessSegment,
    PrimaryRequirement,
    RecommendationResponse,
)

ApplicantBusinessType = Literal[
    "Micro retail",
    "Professional office",
    "Multi-site business",
    "Manufacturing",
]
GstinSelfReportedStatus = Literal["Verified", "Not verified", "Not registered"]


class ApplicantProfile(BaseModel):
    """The business facts retained for one applicant's prototype journey."""

    model_config = ConfigDict(frozen=True)

    business_name: str = Field(min_length=1, max_length=200)
    business_type: ApplicantBusinessType
    city: str = Field(min_length=1, max_length=120)
    business_profile: BusinessProfile
    business_segment: BusinessSegment
    gstin_self_reported_status: GstinSelfReportedStatus
    primary_requirements: list[PrimaryRequirement] = Field(min_length=1)

    @field_validator("business_name", "city")
    @classmethod
    def text_fields_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank.")
        return value

    @field_validator("primary_requirements")
    @classmethod
    def requirements_must_be_unique(
        cls, requirements: list[PrimaryRequirement]
    ) -> list[PrimaryRequirement]:
        if len(requirements) != len(set(requirements)):
            raise ValueError("primary_requirements must not contain duplicates.")
        return requirements

    @model_validator(mode="after")
    def gstin_flag_must_match_self_report(self) -> "ApplicantProfile":
        expected_verified = self.gstin_self_reported_status == "Verified"
        if self.business_profile.gstin_verified != expected_verified:
            raise ValueError(
                "business_profile.gstin_verified must match the self-reported GSTIN status."
            )
        return self


class ApplicantRecord(BaseModel):
    """A saved applicant profile and its initial deterministic recommendations."""

    model_config = ConfigDict(frozen=True)

    applicant_id: str
    created_at: str
    profile: ApplicantProfile
    recommendations: RecommendationResponse
    latest_quote: QuoteResponse | None = None


class ApplicantJourneyResponse(BaseModel):
    """Response returned after an onboarding profile begins a journey."""

    model_config = ConfigDict(frozen=True)

    applicant: ApplicantRecord
    recommendations: RecommendationResponse


class ApplicantQuotePreviewRequest(BaseModel):
    """Selections to quote against the saved applicant business profile."""

    model_config = ConfigDict(frozen=True)

    selected_products: list[ProductSelection]

    @field_validator("selected_products")
    @classmethod
    def selected_products_must_not_be_empty(
        cls, products: list[ProductSelection]
    ) -> list[ProductSelection]:
        if not products:
            raise ValueError("A quote must contain at least one product selection.")
        return products


class ApplicantQuotePreviewResponse(BaseModel):
    """A saved applicant-scoped quote preview."""

    model_config = ConfigDict(frozen=True)

    applicant_id: str
    quote: QuoteResponse
