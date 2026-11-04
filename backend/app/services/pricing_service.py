"""Deterministic quote calculation from the catalogue and eligibility engine."""

from collections.abc import Iterable

from app.models.pricing import QuoteLineItem, QuoteRequest, QuoteResponse
from app.models.product import Product
from app.services.catalogue_loader import load_catalogue
from app.services.eligibility_service import evaluate_bundle_eligibility


class PricingValidationError(ValueError):
    """Raised when a quote cannot be produced for the requested bundle."""


def _validate_selections(request: QuoteRequest) -> None:
    if not request.selected_products:
        raise PricingValidationError("A quote must contain at least one product selection.")

    product_ids = [selection.product_id for selection in request.selected_products]
    duplicate_ids = sorted(
        {product_id for product_id in product_ids if product_ids.count(product_id) > 1}
    )
    if duplicate_ids:
        raise PricingValidationError(
            "Duplicate product selections are not allowed: "
            f"{', '.join(duplicate_ids)}."
        )


def _raise_for_ineligible_bundle(request: QuoteRequest, products: list[Product]) -> None:
    product_ids = [selection.product_id for selection in request.selected_products]
    eligibility_results = evaluate_bundle_eligibility(
        product_ids, products, request.business_profile
    )
    rejected_results = [
        result for result in eligibility_results if not result.is_eligible
    ]
    if not rejected_results:
        return

    details: list[str] = []
    for result in rejected_results:
        reasons = "; ".join(result.rejection_reasons)
        if result.missing_dependencies:
            reasons = (
                f"{reasons} Missing prerequisites: "
                f"{', '.join(result.missing_dependencies)}."
            )
        details.append(f"{result.product_id}: {reasons}")
    raise PricingValidationError(
        "Quote cannot be generated because selected products are ineligible. "
        + " ".join(details)
    )


def generate_quote(
    request: QuoteRequest, catalogue: Iterable[Product] | None = None
) -> QuoteResponse:
    """Validate a bundle and calculate its monthly and setup INR totals.

    Each line retains its source product's minimum contract duration. The quote
    intentionally does not derive a single contract duration for the bundle.
    """
    _validate_selections(request)
    products = list(load_catalogue() if catalogue is None else catalogue)
    _raise_for_ineligible_bundle(request, products)
    products_by_id = {product.product_id: product for product in products}

    line_items: list[QuoteLineItem] = []
    for selection in request.selected_products:
        product = products_by_id[selection.product_id]
        line_items.append(
            QuoteLineItem(
                product_id=product.product_id,
                category=product.category,
                product_name=product.product_name,
                description=product.description,
                unit=product.unit,
                quantity=selection.quantity,
                monthly_unit_price_min_inr=product.price_min_inr_per_month,
                monthly_unit_price_max_inr=product.price_max_inr_per_month,
                monthly_subtotal_min_inr=(
                    product.price_min_inr_per_month * selection.quantity
                ),
                monthly_subtotal_max_inr=(
                    product.price_max_inr_per_month * selection.quantity
                ),
                one_time_setup_fee_per_unit_inr=product.one_time_setup_inr,
                one_time_setup_subtotal_inr=(
                    product.one_time_setup_inr * selection.quantity
                ),
                min_contract_months=product.min_contract_months,
            )
        )

    return QuoteResponse(
        line_items=line_items,
        total_monthly_min_inr=sum(
            item.monthly_subtotal_min_inr for item in line_items
        ),
        total_monthly_max_inr=sum(
            item.monthly_subtotal_max_inr for item in line_items
        ),
        total_one_time_setup_inr=sum(
            item.one_time_setup_subtotal_inr for item in line_items
        ),
    )
