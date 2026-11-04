"""Typed product representation for the catalogue."""

from pydantic import BaseModel, ConfigDict, Field


class Product(BaseModel):
    """A product record loaded from the UdyamOne catalogue CSV."""

    model_config = ConfigDict(frozen=True)

    product_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    price_min_inr_per_month: int = Field(ge=0)
    price_max_inr_per_month: int = Field(ge=0)
    one_time_setup_inr: int = Field(ge=0)
    min_contract_months: int = Field(ge=0)
    available_city_tiers: list[int] = Field(min_length=1)
    min_employees: int = Field(ge=1)
    min_sites: int = Field(ge=1)
    requires_gstin: bool
    requires_one_of: list[str]
    typical_install_days: int = Field(ge=0)
    target_segments: list[str] = Field(min_length=1)
