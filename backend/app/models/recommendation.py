"""Typed request and response models for catalogue-backed recommendations."""

from typing import Literal

from pydantic import BaseModel, Field, StrictInt, field_validator

from app.models.business_profile import BusinessProfile

BusinessSegment = Literal["micro", "prof", "multi", "mfg"]
PrimaryRequirement = Literal[
    "connectivity",
    "business_communication",
    "cloud_productivity",
    "security_iot",
]
BundleType = Literal["budget", "recommended", "advanced"]


class RecommendationRequest(BaseModel):
    """Business context and customer priorities used to rank catalogue products."""

    business_profile: BusinessProfile
    business_segment: BusinessSegment
    primary_requirements: list[PrimaryRequirement] = Field(min_length=1)

    @field_validator("primary_requirements")
    @classmethod
    def requirements_must_be_unique(
        cls, requirements: list[PrimaryRequirement]
    ) -> list[PrimaryRequirement]:
        if len(requirements) != len(set(requirements)):
            raise ValueError("primary_requirements must not contain duplicates.")
        return requirements


class RecommendedProduct(BaseModel):
    """One product in an explainable recommendation bundle."""

    product_id: str
    category: str
    product_name: str
    description: str
    unit: str
    quantity: StrictInt = Field(gt=0)
    recommendation_reason: str
    is_required_prerequisite: bool
    required_for_product_ids: list[str] = Field(default_factory=list)
    monthly_min_inr: int = Field(ge=0)
    monthly_max_inr: int = Field(ge=0)
    one_time_setup_inr: int = Field(ge=0)
    min_contract_months: int = Field(ge=0)


class RecommendationBundle(BaseModel):
    """A complete, quoteable option created from eligible catalogue products."""

    bundle_id: str
    bundle_type: BundleType
    display_name: str
    explanation: str
    products: list[RecommendedProduct] = Field(min_length=1)
    supported_requirements: list[PrimaryRequirement]
    unsupported_requirements: list[PrimaryRequirement]
    limitations: list[str] = Field(default_factory=list)
    monthly_min_inr: int = Field(ge=0)
    monthly_max_inr: int = Field(ge=0)
    one_time_setup_inr: int = Field(ge=0)


class RecommendationResponse(BaseModel):
    """All valid recommendation options for the submitted business profile."""

    bundles: list[RecommendationBundle]
    unsupported_requirements: list[PrimaryRequirement]
    limitations: list[str] = Field(default_factory=list)
