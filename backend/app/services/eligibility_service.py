"""Deterministic catalogue eligibility and bundle dependency checks."""

from collections.abc import Iterable, Mapping

from app.models.business_profile import BusinessProfile
from app.models.eligibility import BundleDependencyValidation, EligibilityResult
from app.models.product import Product


def check_product_eligibility(
    product: Product, profile: BusinessProfile
) -> EligibilityResult:
    """Evaluate business-profile constraints for one product only.

    Bundle prerequisites are deliberately excluded from this check so callers can
    distinguish product eligibility from bundle composition errors.
    """
    rejection_reasons: list[str] = []

    if profile.city_tier not in product.available_city_tiers:
        supported_tiers = ", ".join(str(tier) for tier in product.available_city_tiers)
        rejection_reasons.append(
            f"City tier {profile.city_tier} is not supported; supported tiers: "
            f"{supported_tiers}."
        )
    if profile.employee_count < product.min_employees:
        rejection_reasons.append(
            f"Employee count {profile.employee_count} is below the required minimum "
            f"of {product.min_employees}."
        )
    if profile.site_count < product.min_sites:
        rejection_reasons.append(
            f"Site count {profile.site_count} is below the required minimum "
            f"of {product.min_sites}."
        )
    if product.requires_gstin and not profile.gstin_verified:
        rejection_reasons.append(
            "Verification against the synthetic GSTIN competition registry is required."
        )

    return EligibilityResult(
        product_id=product.product_id,
        is_eligible=not rejection_reasons,
        rejection_reasons=rejection_reasons,
    )


def validate_bundle_dependencies(
    selected_product_ids: Iterable[str],
    products_by_id: Mapping[str, Product],
    individual_results: Mapping[str, EligibilityResult],
) -> dict[str, BundleDependencyValidation]:
    """Validate selected prerequisite products independently of profile checks.

    A product with ``requires_one_of`` is satisfied when at least one listed
    prerequisite is selected *and* individually eligible for the business.
    """
    selected_ids = set(selected_product_ids)
    validations: dict[str, BundleDependencyValidation] = {}

    for product_id in selected_ids:
        product = products_by_id.get(product_id)
        if product is None:
            continue

        if not product.requires_one_of:
            validations[product_id] = BundleDependencyValidation(
                product_id=product_id,
                dependencies_satisfied=True,
            )
            continue

        selected_dependencies = [
            dependency_id
            for dependency_id in product.requires_one_of
            if dependency_id in selected_ids
        ]
        if not selected_dependencies:
            validations[product_id] = BundleDependencyValidation(
                product_id=product_id,
                dependencies_satisfied=False,
                rejection_reasons=[
                    "At least one prerequisite must be selected: "
                    f"{', '.join(product.requires_one_of)}."
                ],
                missing_dependencies=list(product.requires_one_of),
            )
            continue

        eligible_dependencies = [
            dependency_id
            for dependency_id in selected_dependencies
            if individual_results.get(dependency_id, EligibilityResult(
                product_id=dependency_id,
                is_eligible=False,
            )).is_eligible
        ]
        if eligible_dependencies:
            validations[product_id] = BundleDependencyValidation(
                product_id=product_id,
                dependencies_satisfied=True,
            )
            continue

        validations[product_id] = BundleDependencyValidation(
            product_id=product_id,
            dependencies_satisfied=False,
            rejection_reasons=[
                "No selected prerequisite is eligible for this business: "
                f"{', '.join(selected_dependencies)}."
            ],
        )

    return validations


def evaluate_bundle_eligibility(
    selected_product_ids: Iterable[str],
    products: Iterable[Product],
    profile: BusinessProfile,
) -> list[EligibilityResult]:
    """Return eligibility decisions for the products selected in one bundle."""
    selected_ids = list(dict.fromkeys(selected_product_ids))
    products_by_id = {product.product_id: product for product in products}
    individual_results = {
        product_id: check_product_eligibility(products_by_id[product_id], profile)
        for product_id in selected_ids
        if product_id in products_by_id
    }
    dependency_validations = validate_bundle_dependencies(
        selected_ids, products_by_id, individual_results
    )

    results: list[EligibilityResult] = []
    for product_id in selected_ids:
        individual_result = individual_results.get(product_id)
        if individual_result is None:
            results.append(
                EligibilityResult(
                    product_id=product_id,
                    is_eligible=False,
                    rejection_reasons=[f"Unknown product ID '{product_id}'."],
                )
            )
            continue

        dependency_validation = dependency_validations[product_id]
        rejection_reasons = [
            *individual_result.rejection_reasons,
            *dependency_validation.rejection_reasons,
        ]
        results.append(
            EligibilityResult(
                product_id=product_id,
                is_eligible=(
                    individual_result.is_eligible
                    and dependency_validation.dependencies_satisfied
                ),
                rejection_reasons=rejection_reasons,
                missing_dependencies=dependency_validation.missing_dependencies,
            )
        )

    return results
