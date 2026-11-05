"""Application service layer."""

from app.services.advisor_service import (
    AdvisorNotConfiguredError,
    AdvisorProviderTimeoutError,
    AdvisorProviderUnavailableError,
    chat_with_advisor,
)
from app.services.catalogue_loader import load_catalogue
from app.services.eligibility_service import (
    check_product_eligibility,
    evaluate_bundle_eligibility,
    validate_bundle_dependencies,
)
from app.services.pricing_service import PricingValidationError, generate_quote
from app.services.recommendation_service import generate_recommendations

__all__ = [
    "AdvisorNotConfiguredError",
    "AdvisorProviderTimeoutError",
    "AdvisorProviderUnavailableError",
    "check_product_eligibility",
    "chat_with_advisor",
    "evaluate_bundle_eligibility",
    "load_catalogue",
    "PricingValidationError",
    "generate_quote",
    "generate_recommendations",
    "validate_bundle_dependencies",
]
