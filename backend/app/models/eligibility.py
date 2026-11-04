"""Structured results returned by the eligibility service."""

from pydantic import BaseModel, Field


class EligibilityResult(BaseModel):
    """Eligibility decision for one selected product."""

    product_id: str
    is_eligible: bool
    rejection_reasons: list[str] = Field(default_factory=list)
    missing_dependencies: list[str] = Field(default_factory=list)


class BundleDependencyValidation(BaseModel):
    """Dependency-only validation outcome for one selected product."""

    product_id: str
    dependencies_satisfied: bool
    rejection_reasons: list[str] = Field(default_factory=list)
    missing_dependencies: list[str] = Field(default_factory=list)
