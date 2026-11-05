"""Tests for deterministic catalogue-backed recommendation bundles."""

import pytest
from pydantic import ValidationError

from app.models.business_profile import BusinessProfile
from app.models.pricing import ProductSelection, QuoteRequest
from app.models.product import Product
from app.models.recommendation import RecommendationRequest
from app.services.catalogue_loader import load_catalogue
from app.services.pricing_service import generate_quote
from app.services.recommendation_service import generate_recommendations


def _request(
    *,
    segment: str = "micro",
    requirements: list[str] | None = None,
    city_tier: int = 1,
    employee_count: int = 1,
    site_count: int = 1,
    gstin_verified: bool = False,
) -> RecommendationRequest:
    return RecommendationRequest(
        business_profile=BusinessProfile(
            city_tier=city_tier,
            employee_count=employee_count,
            site_count=site_count,
            gstin_verified=gstin_verified,
        ),
        business_segment=segment,  # type: ignore[arg-type]
        primary_requirements=requirements or ["connectivity"],  # type: ignore[arg-type]
    )


def _product(
    product_id: str,
    dependencies: list[str] | None = None,
    *,
    category: str = "Connectivity",
    min_employees: int = 1,
    product_name: str | None = None,
    description: str | None = None,
) -> Product:
    return Product(
        product_id=product_id,
        category=category,
        product_name=product_name or f"Product {product_id}",
        description=description or "A test catalogue product.",
        unit="per site",
        price_min_inr_per_month=100,
        price_max_inr_per_month=150,
        one_time_setup_inr=0,
        min_contract_months=1,
        available_city_tiers=[1, 2],
        min_employees=min_employees,
        min_sites=1,
        requires_gstin=False,
        requires_one_of=dependencies or [],
        typical_install_days=1,
        target_segments=["micro"],
    )


def test_recommendations_are_deterministic_for_the_same_profile() -> None:
    request = _request(requirements=["connectivity", "cloud_productivity"])

    first = generate_recommendations(request)
    second = generate_recommendations(request)

    assert first.model_dump() == second.model_dump()
    assert first.bundles


def test_recommended_bundle_uses_business_segment_as_a_ranking_signal() -> None:
    response = generate_recommendations(_request(segment="micro"))
    recommended = next(bundle for bundle in response.bundles if bundle.bundle_type == "recommended")

    assert [product.product_id for product in recommended.products] == ["P07"]


def test_reports_requirements_with_no_eligible_catalogue_support() -> None:
    response = generate_recommendations(
        _request(requirements=["cloud_productivity"], city_tier=3)
    )

    assert response.bundles == []
    assert response.unsupported_requirements == ["cloud_productivity"]


def test_partial_support_excludes_unrelated_products() -> None:
    response = generate_recommendations(
        _request(requirements=["connectivity", "business_communication"])
    )

    assert response.bundles
    assert response.unsupported_requirements == ["business_communication"]
    assert all(
        product.category == "Connectivity"
        for bundle in response.bundles
        for product in bundle.products
    )


def test_ineligible_products_are_excluded_from_recommendations() -> None:
    response = generate_recommendations(
        _request(segment="mfg", employee_count=1, gstin_verified=False)
    )

    assert all(
        product.product_id != "P03"
        for bundle in response.bundles
        for product in bundle.products
    )


def test_dependencies_are_resolved_and_visible_in_bundle_output() -> None:
    catalogue = [
        product
        for product in load_catalogue()
        if product.product_id in {"P01", "P09"}
    ]
    response = generate_recommendations(
        _request(segment="multi", employee_count=1, gstin_verified=False),
        catalogue,
    )
    recommended = next(bundle for bundle in response.bundles if bundle.bundle_type == "recommended")
    products = {product.product_id: product for product in recommended.products}

    assert "P09" in products
    assert products["P01"].is_required_prerequisite is True
    assert products["P01"].required_for_product_ids == ["P09"]


def test_unresolvable_unknown_dependencies_do_not_create_a_bundle() -> None:
    response = generate_recommendations(
        _request(requirements=["business_communication"]),
        [_product("P01", ["P99"], category="Communication")],
    )

    assert response.bundles == []
    assert response.unsupported_requirements == ["business_communication"]
    assert any("'P99'" in limitation for limitation in response.limitations)


def test_alternate_prerequisite_recovers_without_stale_failed_branch_limitations() -> None:
    catalogue = [
        _product("P01", ["P02", "P03"], category="Communication"),
        _product("P02", min_employees=2),
        _product("P03"),
    ]
    response = generate_recommendations(
        _request(requirements=["business_communication"]), catalogue
    )
    recommended = next(bundle for bundle in response.bundles if bundle.bundle_type == "recommended")

    assert [product.product_id for product in recommended.products] == ["P01", "P03"]
    assert all("P02" not in limitation for limitation in recommended.limitations)
    prerequisite = next(product for product in recommended.products if product.product_id == "P03")
    assert prerequisite.is_required_prerequisite is True
    assert prerequisite.required_for_product_ids == ["P01"]


def test_dependency_cycles_do_not_create_a_bundle() -> None:
    response = generate_recommendations(
        _request(),
        [_product("P01", ["P02"]), _product("P02", ["P01"])],
    )

    assert response.bundles == []
    assert any("Dependency cycle detected" in limitation for limitation in response.limitations)


def test_recommendation_quote_totals_match_the_pricing_engine() -> None:
    catalogue = load_catalogue()
    request = _request(segment="multi")
    response = generate_recommendations(request, catalogue)
    bundle = next(bundle for bundle in response.bundles if bundle.bundle_type == "recommended")
    quote = generate_quote(
        QuoteRequest(
            business_profile=request.business_profile,
            selected_products=[
                ProductSelection(product_id=product.product_id, quantity=1)
                for product in bundle.products
            ],
        ),
        catalogue,
    )

    assert bundle.monthly_min_inr == quote.total_monthly_min_inr
    assert bundle.monthly_max_inr == quote.total_monthly_max_inr
    assert bundle.one_time_setup_inr == quote.total_one_time_setup_inr


def test_bundle_configurations_are_unique_and_advanced_is_meaningfully_distinct() -> None:
    response = generate_recommendations(_request(requirements=["connectivity"]))
    signatures = [
        tuple(sorted(product.product_id for product in bundle.products))
        for bundle in response.bundles
    ]

    assert len(signatures) == len(set(signatures))
    recommended = next(bundle for bundle in response.bundles if bundle.bundle_type == "recommended")
    advanced = next(
        (bundle for bundle in response.bundles if bundle.bundle_type == "advanced"),
        None,
    )
    if advanced is not None:
        assert advanced.supported_requirements == recommended.supported_requirements
        assert {
            product.product_id for product in advanced.products
        } != {product.product_id for product in recommended.products}


def test_rejects_duplicate_requested_requirements() -> None:
    with pytest.raises(ValidationError, match="must not contain duplicates"):
        _request(requirements=["connectivity", "connectivity"])
