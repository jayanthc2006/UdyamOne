"""Tests for deterministic business and bundle eligibility decisions."""

import pytest

from app.models.business_profile import BusinessProfile
from app.services.catalogue_loader import load_catalogue
from app.services.eligibility_service import (
    check_product_eligibility,
    evaluate_bundle_eligibility,
)


@pytest.fixture
def catalogue():
    return load_catalogue()


def _product(catalogue, product_id: str):
    return next(product for product in catalogue if product.product_id == product_id)


def _result(results, product_id: str):
    return next(result for result in results if result.product_id == product_id)


def test_product_is_eligible_when_profile_meets_catalogue_requirements(catalogue) -> None:
    result = check_product_eligibility(
        _product(catalogue, "P01"),
        BusinessProfile(
            city_tier=1, employee_count=1, site_count=1, gstin_verified=False
        ),
    )

    assert result.is_eligible is True
    assert result.rejection_reasons == []


def test_rejects_unsupported_city_tier(catalogue) -> None:
    result = check_product_eligibility(
        _product(catalogue, "P03"),
        BusinessProfile(
            city_tier=2, employee_count=5, site_count=1, gstin_verified=True
        ),
    )

    assert result.is_eligible is False
    assert result.rejection_reasons == [
        "City tier 2 is not supported; supported tiers: 1."
    ]


def test_rejects_insufficient_employee_count(catalogue) -> None:
    result = check_product_eligibility(
        _product(catalogue, "P05"),
        BusinessProfile(
            city_tier=1, employee_count=9, site_count=1, gstin_verified=True
        ),
    )

    assert result.is_eligible is False
    assert "Employee count 9 is below the required minimum of 10." in result.rejection_reasons


def test_rejects_insufficient_site_count(catalogue) -> None:
    result = check_product_eligibility(
        _product(catalogue, "P10"),
        BusinessProfile(
            city_tier=1, employee_count=10, site_count=2, gstin_verified=True
        ),
    )

    assert result.is_eligible is False
    assert "Site count 2 is below the required minimum of 3." in result.rejection_reasons


def test_rejects_product_requiring_unverified_gstin(catalogue) -> None:
    result = check_product_eligibility(
        _product(catalogue, "P03"),
        BusinessProfile(
            city_tier=1, employee_count=5, site_count=1, gstin_verified=False
        ),
    )

    assert result.is_eligible is False
    assert result.rejection_reasons == [
        "Verification against the synthetic GSTIN competition registry is required."
    ]


def test_product_without_dependencies_is_bundle_eligible(catalogue) -> None:
    results = evaluate_bundle_eligibility(
        ["P01"],
        catalogue,
        BusinessProfile(
            city_tier=1, employee_count=1, site_count=1, gstin_verified=False
        ),
    )

    assert _result(results, "P01").model_dump() == {
        "product_id": "P01",
        "is_eligible": True,
        "rejection_reasons": [],
        "missing_dependencies": [],
    }


def test_bundle_reports_missing_prerequisites(catalogue) -> None:
    results = evaluate_bundle_eligibility(
        ["P09"],
        catalogue,
        BusinessProfile(
            city_tier=1, employee_count=1, site_count=1, gstin_verified=False
        ),
    )
    result = _result(results, "P09")

    assert result.is_eligible is False
    assert result.missing_dependencies == ["P01", "P02", "P03", "P05", "P06"]
    assert "At least one prerequisite must be selected" in result.rejection_reasons[0]


def test_bundle_accepts_multiple_valid_prerequisite_choices(catalogue) -> None:
    results = evaluate_bundle_eligibility(
        ["P09", "P01", "P02"],
        catalogue,
        BusinessProfile(
            city_tier=1, employee_count=1, site_count=1, gstin_verified=False
        ),
    )

    assert _result(results, "P09").is_eligible is True


def test_bundle_rejects_an_ineligible_selected_prerequisite(catalogue) -> None:
    results = evaluate_bundle_eligibility(
        ["P09", "P05"],
        catalogue,
        BusinessProfile(
            city_tier=1, employee_count=1, site_count=1, gstin_verified=True
        ),
    )

    assert _result(results, "P05").is_eligible is False
    dependent_result = _result(results, "P09")
    assert dependent_result.is_eligible is False
    assert dependent_result.missing_dependencies == []
    assert "No selected prerequisite is eligible" in dependent_result.rejection_reasons[0]


def test_bundle_reports_unknown_selected_product_ids(catalogue) -> None:
    results = evaluate_bundle_eligibility(
        ["P99"],
        catalogue,
        BusinessProfile(
            city_tier=1, employee_count=1, site_count=1, gstin_verified=False
        ),
    )

    assert results[0].is_eligible is False
    assert results[0].rejection_reasons == ["Unknown product ID 'P99'."]


def test_returns_all_individual_rejection_reasons(catalogue) -> None:
    result = check_product_eligibility(
        _product(catalogue, "P03"),
        BusinessProfile(
            city_tier=2, employee_count=2, site_count=0, gstin_verified=False
        ),
    )

    assert result.is_eligible is False
    assert result.rejection_reasons == [
        "City tier 2 is not supported; supported tiers: 1.",
        "Employee count 2 is below the required minimum of 5.",
        "Site count 0 is below the required minimum of 1.",
        "Verification against the synthetic GSTIN competition registry is required.",
    ]
