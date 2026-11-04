"""HTTP request and response schemas for catalogue operations."""

from pydantic import BaseModel, Field

from app.models.business_profile import BusinessProfile
from app.models.eligibility import EligibilityResult
from app.models.product import Product


class ProductListResponse(BaseModel):
    """Structured response containing the full product catalogue."""

    products: list[Product]


class EligibilityCheckRequest(BaseModel):
    """Business context and selected product IDs for bundle validation."""

    business_profile: BusinessProfile
    selected_product_ids: list[str] = Field(min_length=1)


class EligibilityCheckResponse(BaseModel):
    """Per-product bundle eligibility outcomes."""

    results: list[EligibilityResult]
