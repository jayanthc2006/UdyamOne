"""Deterministic, catalogue-backed product recommendation service.

Requirement mapping is deliberately based on the real ``category`` values in
``product_catalogue.csv``:

* ``connectivity`` -> ``Connectivity``
* ``business_communication`` -> ``Communication``
* ``cloud_productivity`` -> ``Cloud & Productivity``
* ``security_iot`` -> ``Security`` and ``IoT & Physical``

Product IDs are never recommendation rules. ``target_segments`` only ranks
eligible products; it does not exclude a product from consideration.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

from app.models.eligibility import EligibilityResult
from app.models.pricing import ProductSelection, QuoteRequest, QuoteResponse
from app.models.product import Product
from app.models.recommendation import (
    PrimaryRequirement,
    RecommendedProduct,
    RecommendationBundle,
    RecommendationRequest,
    RecommendationResponse,
)
from app.services.catalogue_loader import load_catalogue
from app.services.eligibility_service import check_product_eligibility, evaluate_bundle_eligibility
from app.services.pricing_service import PricingValidationError, generate_quote

REQUIREMENT_CATEGORY_MAP: dict[PrimaryRequirement, tuple[str, ...]] = {
    "connectivity": ("Connectivity",),
    "business_communication": ("Communication",),
    "cloud_productivity": ("Cloud & Productivity",),
    "security_iot": ("Security", "IoT & Physical"),
}

REQUIREMENT_LABELS: dict[PrimaryRequirement, str] = {
    "connectivity": "Connectivity",
    "business_communication": "Business communication",
    "cloud_productivity": "Cloud and productivity",
    "security_iot": "Security and IoT",
}

BUNDLE_METADATA = {
    "budget": (
        "Budget-friendly",
        "The lowest-cost eligible catalogue combination that covers your supported priorities.",
    ),
    "recommended": (
        "Recommended",
        "The strongest overall match, prioritising your selected business segment before cost.",
    ),
    "advanced": (
        "Advanced",
        "A distinct eligible catalogue alternative where the available products support one.",
    ),
}

RecommendationStrategy = Literal["budget", "recommended", "advanced"]
_BundleSnapshot = tuple[
    dict[str, Product],
    dict[str, set[str]],
    dict[str, list[str]],
    list[str],
]


@dataclass
class _ResolvedBundle:
    products: dict[str, Product] = field(default_factory=dict)
    required_for: dict[str, set[str]] = field(default_factory=dict)
    reasons: dict[str, list[str]] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)

    def snapshot(self) -> _BundleSnapshot:
        return (
            dict(self.products),
            {product_id: set(parent_ids) for product_id, parent_ids in self.required_for.items()},
            {product_id: list(reasons) for product_id, reasons in self.reasons.items()},
            list(self.limitations),
        )

    def restore(
        self, snapshot: _BundleSnapshot
    ) -> None:
        self.products, self.required_for, self.reasons, self.limitations = snapshot


def _is_eligible(product: Product, request: RecommendationRequest) -> bool:
    return check_product_eligibility(product, request.business_profile).is_eligible


def _product_sort_key(
    product: Product, request: RecommendationRequest, strategy: RecommendationStrategy
) -> tuple[int | str, ...]:
    segment_match = request.business_segment in product.target_segments
    if strategy == "budget":
        return (
            product.price_min_inr_per_month,
            product.one_time_setup_inr,
            product.price_max_inr_per_month,
            product.product_id,
        )
    if strategy == "advanced":
        return (
            0 if segment_match else 1,
            -product.price_min_inr_per_month,
            -product.price_max_inr_per_month,
            -product.one_time_setup_inr,
            product.product_id,
        )
    return (
        0 if segment_match else 1,
        product.price_min_inr_per_month,
        product.one_time_setup_inr,
        product.price_max_inr_per_month,
        product.product_id,
    )


def _candidate_products(
    requirement: PrimaryRequirement,
    products: Iterable[Product],
    request: RecommendationRequest,
    strategy: RecommendationStrategy,
) -> list[Product]:
    categories = REQUIREMENT_CATEGORY_MAP[requirement]
    candidates = [
        product
        for product in products
        if product.category in categories and _is_eligible(product, request)
    ]
    return sorted(candidates, key=lambda product: _product_sort_key(product, request, strategy))


def _add_reason(bundle: _ResolvedBundle, product_id: str, reason: str) -> None:
    reasons = bundle.reasons.setdefault(product_id, [])
    if reason not in reasons:
        reasons.append(reason)


def _resolve_product(
    product_id: str,
    *,
    products_by_id: dict[str, Product],
    request: RecommendationRequest,
    strategy: RecommendationStrategy,
    bundle: _ResolvedBundle,
    stack: tuple[str, ...] = (),
    required_for_product_id: str | None = None,
) -> bool:
    """Recursively include one product and one valid prerequisite path."""
    if product_id in stack:
        cycle = " -> ".join([*stack, product_id])
        bundle.limitations.append(f"Dependency cycle detected: {cycle}.")
        return False

    product = products_by_id.get(product_id)
    if product is None:
        bundle.limitations.append(
            f"Catalogue dependency '{product_id}' could not be found."
        )
        return False
    if not _is_eligible(product, request):
        bundle.limitations.append(
            f"Prerequisite '{product.product_name}' is not eligible for this business profile."
        )
        return False

    if product_id in bundle.products:
        if required_for_product_id:
            bundle.required_for.setdefault(product_id, set()).add(required_for_product_id)
        return True

    snapshot = bundle.snapshot()
    bundle.products[product_id] = product
    if required_for_product_id:
        bundle.required_for.setdefault(product_id, set()).add(required_for_product_id)
        _add_reason(
            bundle,
            product_id,
            f"Required because it satisfies a catalogue prerequisite for {required_for_product_id}.",
        )

    if not product.requires_one_of:
        return True

    dependency_ids = sorted(
        product.requires_one_of,
        key=lambda dependency: (
            0 if dependency in bundle.products else 1,
            _product_sort_key(products_by_id[dependency], request, strategy)
            if dependency in products_by_id
            else (0,),
        ),
    )
    dependency_failures: list[str] = []
    for dependency_id in dependency_ids:
        branch = bundle.snapshot()
        if _resolve_product(
            dependency_id,
            products_by_id=products_by_id,
            request=request,
            strategy=strategy,
            bundle=bundle,
            stack=(*stack, product_id),
            required_for_product_id=product_id,
        ):
            return True
        dependency_failures.extend(
            limitation for limitation in bundle.limitations if limitation not in branch[3]
        )
        bundle.restore(branch)

    bundle.restore(snapshot)
    bundle.limitations.extend(dict.fromkeys(dependency_failures))
    bundle.limitations.append(
        f"No eligible prerequisite could be resolved for '{product.product_name}'."
    )
    return False


def _build_bundle(
    request: RecommendationRequest,
    products: list[Product],
    strategy: RecommendationStrategy,
) -> tuple[_ResolvedBundle, list[PrimaryRequirement]]:
    products_by_id = {product.product_id: product for product in products}
    bundle = _ResolvedBundle()
    unsupported: list[PrimaryRequirement] = []

    for requirement in request.primary_requirements:
        candidates = _candidate_products(requirement, products, request, strategy)
        if not candidates:
            unsupported.append(requirement)
            bundle.limitations.append(
                f"No eligible catalogue product currently supports {REQUIREMENT_LABELS[requirement]}."
            )
            continue

        resolved = False
        candidate_failures: list[str] = []
        for candidate in candidates:
            branch = bundle.snapshot()
            if _resolve_product(
                candidate.product_id,
                products_by_id=products_by_id,
                request=request,
                strategy=strategy,
                bundle=bundle,
            ):
                segment_reason = (
                    f"Its catalogue target segments include {request.business_segment}."
                    if request.business_segment in candidate.target_segments
                    else "It is eligible and matches this selected business requirement."
                )
                _add_reason(
                    bundle,
                    candidate.product_id,
                    f"Matches {REQUIREMENT_LABELS[requirement]}. {segment_reason}",
                )
                resolved = True
                break
            candidate_failures.extend(
                limitation for limitation in bundle.limitations if limitation not in branch[3]
            )
            bundle.restore(branch)
        if not resolved:
            unsupported.append(requirement)
            bundle.limitations.extend(dict.fromkeys(candidate_failures))
            bundle.limitations.append(
                f"No complete eligible dependency path was found for {REQUIREMENT_LABELS[requirement]}."
            )

    return bundle, unsupported


def _is_meaningfully_advanced(
    bundle: _ResolvedBundle,
    unsupported: list[PrimaryRequirement],
    recommended_bundle: _ResolvedBundle,
    recommended_unsupported: list[PrimaryRequirement],
) -> bool:
    """Require equal coverage and a distinct catalogue product alternative.

    A higher charge alone is not evidence of a higher-tier recommendation. A
    distinct product name or description is catalogue evidence of a different
    offer for the same supported needs.
    """
    if not bundle.products or unsupported != recommended_unsupported:
        return False
    if set(bundle.products) == set(recommended_bundle.products):
        return False

    recommended_names = {
        product.product_name for product in recommended_bundle.products.values()
    }
    recommended_descriptions = {
        product.description for product in recommended_bundle.products.values()
    }
    return any(
        product.product_name not in recommended_names
        or product.description not in recommended_descriptions
        for product in bundle.products.values()
    )


def _to_recommendation_bundle(
    bundle: _ResolvedBundle,
    unsupported: list[PrimaryRequirement],
    request: RecommendationRequest,
    bundle_type: RecommendationStrategy,
    products: list[Product],
) -> RecommendationBundle | None:
    if not bundle.products:
        return None

    selected_ids = list(bundle.products)
    eligibility_results: list[EligibilityResult] = evaluate_bundle_eligibility(
        selected_ids, products, request.business_profile
    )
    rejected_results = [result for result in eligibility_results if not result.is_eligible]
    if rejected_results:
        bundle.limitations.extend(
            f"{result.product_id}: {'; '.join(result.rejection_reasons)}"
            for result in rejected_results
        )
        return None

    try:
        quote: QuoteResponse = generate_quote(
            QuoteRequest(
                business_profile=request.business_profile,
                selected_products=[
                    ProductSelection(product_id=product_id, quantity=1)
                    for product_id in selected_ids
                ],
            ),
            products,
        )
    except PricingValidationError as error:
        bundle.limitations.append(str(error))
        return None

    line_items_by_id = {line_item.product_id: line_item for line_item in quote.line_items}
    recommended_products: list[RecommendedProduct] = []
    for product_id, product in bundle.products.items():
        line_item = line_items_by_id[product_id]
        required_for = sorted(bundle.required_for.get(product_id, set()))
        recommended_products.append(
            RecommendedProduct(
                product_id=product.product_id,
                category=product.category,
                product_name=product.product_name,
                description=product.description,
                unit=product.unit,
                quantity=1,
                recommendation_reason=" ".join(bundle.reasons.get(product_id, [
                    "Included as an eligible catalogue prerequisite.",
                ])),
                is_required_prerequisite=bool(required_for),
                required_for_product_ids=required_for,
                monthly_min_inr=line_item.monthly_subtotal_min_inr,
                monthly_max_inr=line_item.monthly_subtotal_max_inr,
                one_time_setup_inr=line_item.one_time_setup_subtotal_inr,
                min_contract_months=line_item.min_contract_months,
            )
        )

    display_name, explanation = BUNDLE_METADATA[bundle_type]
    supported = [
        requirement
        for requirement in request.primary_requirements
        if requirement not in unsupported
    ]
    return RecommendationBundle(
        bundle_id=f"{bundle_type}-bundle",
        bundle_type=bundle_type,
        display_name=display_name,
        explanation=explanation,
        products=recommended_products,
        supported_requirements=supported,
        unsupported_requirements=unsupported,
        limitations=list(dict.fromkeys(bundle.limitations)),
        monthly_min_inr=quote.total_monthly_min_inr,
        monthly_max_inr=quote.total_monthly_max_inr,
        one_time_setup_inr=quote.total_one_time_setup_inr,
    )


def generate_recommendations(
    request: RecommendationRequest, catalogue: Iterable[Product] | None = None
) -> RecommendationResponse:
    """Generate the valid, non-fabricated bundle options supported by the catalogue."""
    products = list(load_catalogue() if catalogue is None else catalogue)
    results: list[RecommendationBundle] = []
    seen_signatures: set[tuple[str, ...]] = set()
    overall_limitations: list[str] = []

    bundles_by_strategy: dict[
        RecommendationStrategy, tuple[_ResolvedBundle, list[PrimaryRequirement]]
    ] = {}
    for strategy in ("recommended", "budget", "advanced"):
        bundle, unsupported = _build_bundle(request, products, strategy)
        bundles_by_strategy[strategy] = (bundle, unsupported)

    recommended_bundle, recommended_unsupported = bundles_by_strategy["recommended"]
    for strategy in ("recommended", "budget", "advanced"):
        bundle, unsupported = bundles_by_strategy[strategy]
        if strategy == "advanced" and not _is_meaningfully_advanced(
            bundle,
            unsupported,
            recommended_bundle,
            recommended_unsupported,
        ):
            overall_limitations.append(
                "No distinct catalogue alternative is available for an advanced option."
            )
            continue
        recommendation_bundle = _to_recommendation_bundle(
            bundle, unsupported, request, strategy, products
        )
        if recommendation_bundle is None:
            overall_limitations.extend(bundle.limitations)
            continue
        signature = tuple(sorted(product.product_id for product in recommendation_bundle.products))
        if signature in seen_signatures:
            overall_limitations.append(
                f"No distinct {recommendation_bundle.display_name} option is available for this profile."
            )
            continue
        seen_signatures.add(signature)
        results.append(recommendation_bundle)

    all_unsupported = list(
        dict.fromkeys(
            requirement
            for _, unsupported in bundles_by_strategy.values()
            for requirement in unsupported
        )
    )
    return RecommendationResponse(
        bundles=results,
        unsupported_requirements=all_unsupported,
        limitations=list(dict.fromkeys(overall_limitations)),
    )
