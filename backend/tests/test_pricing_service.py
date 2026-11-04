"""Tests for deterministic catalogue quote generation."""

import pytest
from pydantic import ValidationError

from app.models.business_profile import BusinessProfile
from app.models.pricing import ProductSelection, QuoteRequest
from app.services.catalogue_loader import load_catalogue
from app.services.pricing_service import PricingValidationError, generate_quote


@pytest.fixture
def catalogue():
    return load_catalogue()


@pytest.fixture
def basic_profile() -> BusinessProfile:
    return BusinessProfile(
        city_tier=1, employee_count=1, site_count=1, gstin_verified=False
    )


def _request(
    profile: BusinessProfile, *selections: ProductSelection
) -> QuoteRequest:
    return QuoteRequest(business_profile=profile, selected_products=list(selections))


def _line_item(quote, product_id: str):
    return next(item for item in quote.line_items if item.product_id == product_id)


def test_prices_a_single_product(catalogue, basic_profile) -> None:
    quote = generate_quote(
        _request(basic_profile, ProductSelection(product_id="P01", quantity=1)),
        catalogue,
    )

    assert quote.total_monthly_min_inr == 999
    assert quote.total_monthly_max_inr == 1199
    assert quote.total_one_time_setup_inr == 0
    assert _line_item(quote, "P01").product_name == "Biz Fibre 100"


def test_prices_multiple_products_and_quote_totals(catalogue, basic_profile) -> None:
    quote = generate_quote(
        _request(
            basic_profile,
            ProductSelection(product_id="P01", quantity=2),
            ProductSelection(product_id="P02", quantity=1),
        ),
        catalogue,
    )

    assert quote.total_monthly_min_inr == 3497
    assert quote.total_monthly_max_inr == 4197
    assert quote.total_one_time_setup_inr == 0


def test_scales_monthly_prices_by_quantity(catalogue, basic_profile) -> None:
    quote = generate_quote(
        _request(basic_profile, ProductSelection(product_id="P01", quantity=3)),
        catalogue,
    )
    line_item = _line_item(quote, "P01")

    assert line_item.monthly_unit_price_min_inr == 999
    assert line_item.monthly_unit_price_max_inr == 1199
    assert line_item.monthly_subtotal_min_inr == 2997
    assert line_item.monthly_subtotal_max_inr == 3597


def test_scales_setup_fees_by_quantity(catalogue, basic_profile) -> None:
    quote = generate_quote(
        _request(
            basic_profile,
            ProductSelection(product_id="P09", quantity=2),
            ProductSelection(product_id="P01", quantity=1),
        ),
        catalogue,
    )
    line_item = _line_item(quote, "P09")

    assert line_item.one_time_setup_fee_per_unit_inr == 1500
    assert line_item.one_time_setup_subtotal_inr == 3000
    assert quote.total_one_time_setup_inr == 3000


def test_preserves_each_product_contract_duration(catalogue) -> None:
    profile = BusinessProfile(
        city_tier=1, employee_count=25, site_count=1, gstin_verified=True
    )
    quote = generate_quote(
        _request(
            profile,
            ProductSelection(product_id="P07", quantity=1),
            ProductSelection(product_id="P06", quantity=1),
        ),
        catalogue,
    )

    assert _line_item(quote, "P07").min_contract_months == 1
    assert _line_item(quote, "P06").min_contract_months == 24


@pytest.mark.parametrize("quantity", [0, -1, "2"])
def test_rejects_zero_or_invalid_quantities(quantity) -> None:
    with pytest.raises(ValidationError):
        ProductSelection(product_id="P01", quantity=quantity)


def test_rejects_duplicate_product_selections(catalogue, basic_profile) -> None:
    request = _request(
        basic_profile,
        ProductSelection(product_id="P01", quantity=1),
        ProductSelection(product_id="P01", quantity=2),
    )

    with pytest.raises(PricingValidationError, match="Duplicate product selections"):
        generate_quote(request, catalogue)


def test_rejects_unknown_product_ids(catalogue, basic_profile) -> None:
    request = _request(
        basic_profile, ProductSelection(product_id="P99", quantity=1)
    )

    with pytest.raises(PricingValidationError, match="P99: Unknown product ID 'P99'"):
        generate_quote(request, catalogue)


def test_rejects_empty_quote_requests(catalogue, basic_profile) -> None:
    request = QuoteRequest(business_profile=basic_profile, selected_products=[])

    with pytest.raises(PricingValidationError, match="at least one product selection"):
        generate_quote(request, catalogue)


def test_rejects_individually_ineligible_business_profiles(catalogue) -> None:
    request = _request(
        BusinessProfile(
            city_tier=2, employee_count=5, site_count=1, gstin_verified=True
        ),
        ProductSelection(product_id="P03", quantity=1),
    )

    with pytest.raises(PricingValidationError, match="City tier 2 is not supported"):
        generate_quote(request, catalogue)


def test_rejects_missing_product_dependencies(catalogue, basic_profile) -> None:
    request = _request(
        basic_profile, ProductSelection(product_id="P09", quantity=1)
    )

    with pytest.raises(PricingValidationError, match="Missing prerequisites: P01, P02, P03, P05, P06"):
        generate_quote(request, catalogue)


def test_rejects_bundle_with_an_ineligible_selected_prerequisite(catalogue) -> None:
    request = _request(
        BusinessProfile(
            city_tier=1, employee_count=1, site_count=1, gstin_verified=True
        ),
        ProductSelection(product_id="P09", quantity=1),
        ProductSelection(product_id="P05", quantity=1),
    )

    with pytest.raises(PricingValidationError, match="No selected prerequisite is eligible"):
        generate_quote(request, catalogue)


def test_prices_valid_eligible_bundle(catalogue, basic_profile) -> None:
    quote = generate_quote(
        _request(
            basic_profile,
            ProductSelection(product_id="P09", quantity=1),
            ProductSelection(product_id="P01", quantity=1),
        ),
        catalogue,
    )

    assert [item.product_id for item in quote.line_items] == ["P09", "P01"]
    assert quote.total_monthly_min_inr == 1498
    assert quote.total_monthly_max_inr == 1798
    assert quote.total_one_time_setup_inr == 1500
