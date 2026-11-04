"""Integration tests for the FastAPI routes."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _basic_profile() -> dict[str, int | bool]:
    return {
        "city_tier": 1,
        "employee_count": 1,
        "site_count": 1,
        "gstin_verified": False,
    }


def test_health_endpoint_remains_available() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_lists_catalogue_products() -> None:
    response = client.get("/api/v1/products")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["products"]) == 25
    assert payload["products"][0]["product_id"] == "P01"


def test_returns_a_catalogue_product_by_id() -> None:
    response = client.get("/api/v1/products/P01")

    assert response.status_code == 200
    assert response.json()["product_name"] == "Biz Fibre 100"


def test_returns_404_for_an_unknown_catalogue_product() -> None:
    response = client.get("/api/v1/products/P99")

    assert response.status_code == 404
    assert response.json()["detail"] == "Product 'P99' was not found."


def test_checks_bundle_eligibility() -> None:
    response = client.post(
        "/api/v1/eligibility/check",
        json={"business_profile": _basic_profile(), "selected_product_ids": ["P01"]},
    )

    assert response.status_code == 200
    assert response.json()["results"] == [
        {
            "product_id": "P01",
            "is_eligible": True,
            "rejection_reasons": [],
            "missing_dependencies": [],
        }
    ]


def test_reports_missing_dependencies_from_eligibility_check() -> None:
    response = client.post(
        "/api/v1/eligibility/check",
        json={"business_profile": _basic_profile(), "selected_product_ids": ["P09"]},
    )

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["is_eligible"] is False
    assert result["missing_dependencies"] == ["P01", "P02", "P03", "P05", "P06"]


def test_rejects_invalid_eligibility_requests() -> None:
    response = client.post(
        "/api/v1/eligibility/check",
        json={"selected_product_ids": ["P01"]},
    )

    assert response.status_code == 422


def test_previews_an_eligible_quote() -> None:
    response = client.post(
        "/api/v1/quotes/preview",
        json={
            "business_profile": _basic_profile(),
            "selected_products": [{"product_id": "P01", "quantity": 2}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_monthly_min_inr"] == 1998
    assert payload["total_monthly_max_inr"] == 2398
    assert payload["total_one_time_setup_inr"] == 0


def test_rejects_quote_with_missing_dependencies() -> None:
    response = client.post(
        "/api/v1/quotes/preview",
        json={
            "business_profile": _basic_profile(),
            "selected_products": [{"product_id": "P09", "quantity": 1}],
        },
    )

    assert response.status_code == 422
    assert "Missing prerequisites: P01, P02, P03, P05, P06" in response.json()["detail"]


def test_rejects_quote_with_unknown_product_id() -> None:
    response = client.post(
        "/api/v1/quotes/preview",
        json={
            "business_profile": _basic_profile(),
            "selected_products": [{"product_id": "P99", "quantity": 1}],
        },
    )

    assert response.status_code == 422
    assert "P99: Unknown product ID 'P99'" in response.json()["detail"]


def test_rejects_ineligible_quotes() -> None:
    response = client.post(
        "/api/v1/quotes/preview",
        json={
            "business_profile": {
                "city_tier": 2,
                "employee_count": 5,
                "site_count": 1,
                "gstin_verified": True,
            },
            "selected_products": [{"product_id": "P03", "quantity": 1}],
        },
    )

    assert response.status_code == 422
    assert "City tier 2 is not supported" in response.json()["detail"]


def test_rejects_invalid_quote_requests() -> None:
    response = client.post(
        "/api/v1/quotes/preview",
        json={
            "business_profile": _basic_profile(),
            "selected_products": [{"product_id": "P01", "quantity": 0}],
        },
    )

    assert response.status_code == 422
