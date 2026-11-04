"""Typed request and response models for deterministic catalogue quotes."""

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.models.business_profile import BusinessProfile


class ProductSelection(BaseModel):
    """A requested quantity for one catalogue product."""

    model_config = ConfigDict(frozen=True)

    product_id: str = Field(min_length=1)
    quantity: StrictInt = Field(gt=0)


class QuoteRequest(BaseModel):
    """Business context and products for a prospective quote."""

    model_config = ConfigDict(frozen=True)

    business_profile: BusinessProfile
    selected_products: list[ProductSelection]


class QuoteLineItem(BaseModel):
    """A calculated quote line for one selected product."""

    model_config = ConfigDict(frozen=True)

    product_id: str
    category: str
    product_name: str
    description: str
    unit: str
    quantity: StrictInt = Field(gt=0)
    monthly_unit_price_min_inr: int = Field(ge=0)
    monthly_unit_price_max_inr: int = Field(ge=0)
    monthly_subtotal_min_inr: int = Field(ge=0)
    monthly_subtotal_max_inr: int = Field(ge=0)
    one_time_setup_fee_per_unit_inr: int = Field(ge=0)
    one_time_setup_subtotal_inr: int = Field(ge=0)
    min_contract_months: int = Field(ge=0)


class QuoteResponse(BaseModel):
    """A validated quote and its aggregate INR amounts."""

    model_config = ConfigDict(frozen=True)

    line_items: list[QuoteLineItem]
    total_monthly_min_inr: int = Field(ge=0)
    total_monthly_max_inr: int = Field(ge=0)
    total_one_time_setup_inr: int = Field(ge=0)
