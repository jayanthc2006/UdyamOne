"""Business information used for product eligibility checks."""

from pydantic import BaseModel, ConfigDict, Field


class BusinessProfile(BaseModel):
    """The business facts relevant to catalogue eligibility."""

    model_config = ConfigDict(frozen=True)

    city_tier: int = Field(ge=1)
    employee_count: int = Field(ge=0)
    site_count: int = Field(ge=0)
    gstin_verified: bool
