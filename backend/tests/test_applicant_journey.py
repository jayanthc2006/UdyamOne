"""Applicant identity integration tests for the onboarding-to-KYC journey."""

import hashlib

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import applicant_service, kyc_service
from app.security.kyc_auth import create_session_token, hash_password, load_kyc_auth_configuration

client = TestClient(app)
_customer_password_hash = hash_password("SyntheticCustomerPassword1!")
_reviewer_password_hash = hash_password("SyntheticReviewerPassword1!")


@pytest.fixture(autouse=True)
def configure_journey_reviewer(monkeypatch) -> None:
    monkeypatch.setenv("UDYAMONE_KYC_AUTH_SECRET", "synthetic-test-signing-secret-not-for-use")
    monkeypatch.setenv(
        "UDYAMONE_KYC_AUTH_USERS",
        (
            '[{"username":"test-customer","role":"CUSTOMER",'
            f'"password_hash":"{_customer_password_hash}","applicant_ids":["K05"]}},'
            '{"username":"test-reviewer","role":"REVIEWER",'
            f'"password_hash":"{_reviewer_password_hash}","applicant_ids":[]}}]'
        ),
    )
    configuration = load_kyc_auth_configuration()
    token, _ = create_session_token(
        configuration.accounts["test-reviewer"], configuration.secret
    )
    client.headers["Authorization"] = f"Bearer {token}"


def _profile(name: str, city: str, business_type: str = "Micro retail") -> dict:
    segment_by_type = {
        "Micro retail": "micro",
        "Professional office": "prof",
        "Multi-site business": "multi",
        "Manufacturing": "mfg",
    }
    return {
        "business_name": name,
        "business_type": business_type,
        "city": city,
        "business_profile": {
            "city_tier": 1,
            "employee_count": 5,
            "site_count": 1,
            "gstin_verified": False,
        },
        "business_segment": segment_by_type[business_type],
        "gstin_self_reported_status": "Not verified",
        "primary_requirements": ["connectivity"],
    }


def _configure_isolated_storage(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        applicant_service, "APPLICANT_DATABASE_PATH", tmp_path / "applicants.sqlite3"
    )
    monkeypatch.setattr(kyc_service, "UPLOAD_ROOT", tmp_path / "kyc_uploads")
    monkeypatch.delenv("UDYAMONE_KYC_REQUIRED_DOCUMENTS", raising=False)


def test_two_applicants_keep_profiles_quotes_and_kyc_state_separate(
    monkeypatch, tmp_path
) -> None:
    _configure_isolated_storage(monkeypatch, tmp_path)
    sample_path = kyc_service.SAMPLE_KYC_ROOT / "K05" / "K05_gst_certificate.png"
    sample_hash = hashlib.sha256(sample_path.read_bytes()).hexdigest()

    applicant_a = client.post(
        "/api/v1/applicants", json=_profile("Asha Traders", "Pune")
    )
    assert applicant_a.status_code == 201
    journey_a = applicant_a.json()
    applicant_a_id = journey_a["applicant"]["applicant_id"]
    assert applicant_a_id.startswith("APPL-")
    assert applicant_a_id != "K05"
    assert journey_a["applicant"]["profile"]["business_name"] == "Asha Traders"
    assert journey_a["applicant"]["profile"]["city"] == "Pune"
    assert journey_a["recommendations"] == journey_a["applicant"]["recommendations"]

    # A browser refresh retrieves the same durable profile and recommendation set.
    restored_a = client.get(f"/api/v1/applicants/{applicant_a_id}")
    assert restored_a.status_code == 200
    assert restored_a.json() == journey_a["applicant"]

    quote_a = client.post(
        f"/api/v1/applicants/{applicant_a_id}/quotes/preview",
        json={"selected_products": [{"product_id": "P01", "quantity": 2}]},
    )
    assert quote_a.status_code == 200
    assert quote_a.json()["applicant_id"] == applicant_a_id
    assert quote_a.json()["quote"]["total_monthly_min_inr"] == 1998
    assert applicant_service.quote_preview_count(applicant_a_id) == 1
    restored_with_quote = client.get(f"/api/v1/applicants/{applicant_a_id}")
    assert restored_with_quote.status_code == 200
    assert restored_with_quote.json()["latest_quote"] == quote_a.json()["quote"]

    kyc_a = client.get(f"/api/v1/kyc/{applicant_a_id}")
    assert kyc_a.status_code == 200
    assert kyc_a.json()["applicant_id"] == applicant_a_id
    assert {document["presence"] for document in kyc_a.json()["documents"]} == {
        "NOT_PROVIDED"
    }
    assert kyc_service._read_manifest(applicant_a_id)["profile"] == {
        "business_name": "Asha Traders",
        "business_address": "Pune",
    }

    applicant_b = client.post(
        "/api/v1/applicants",
        json=_profile("Bharat Office", "Delhi", "Professional office"),
    )
    assert applicant_b.status_code == 201
    applicant_b_id = applicant_b.json()["applicant"]["applicant_id"]
    assert applicant_b_id != applicant_a_id

    restored_b = client.get(f"/api/v1/applicants/{applicant_b_id}")
    assert restored_b.status_code == 200
    assert restored_b.json()["profile"]["business_name"] == "Bharat Office"
    assert restored_b.json()["profile"]["city"] == "Delhi"
    assert applicant_service.quote_preview_count(applicant_b_id) == 0
    kyc_b = client.get(f"/api/v1/kyc/{applicant_b_id}")
    assert kyc_b.status_code == 200
    assert {document["presence"] for document in kyc_b.json()["documents"]} == {
        "NOT_PROVIDED"
    }
    assert kyc_service._read_manifest(applicant_b_id)["profile"] == {
        "business_name": "Bharat Office",
        "business_address": "Delhi",
    }

    # The separate competition fixture is read-only during normal onboarding.
    k05 = client.get("/api/v1/kyc/K05")
    assert k05.status_code == 200
    assert any(document["presence"] == "PROVIDED" for document in k05.json()["documents"])
    assert hashlib.sha256(sample_path.read_bytes()).hexdigest() == sample_hash


def test_profile_update_keeps_applicant_id_and_invalidates_old_quote(
    monkeypatch, tmp_path
) -> None:
    _configure_isolated_storage(monkeypatch, tmp_path)
    created = client.post(
        "/api/v1/applicants", json=_profile("Asha Traders", "Pune")
    )
    applicant_id = created.json()["applicant"]["applicant_id"]
    quote = client.post(
        f"/api/v1/applicants/{applicant_id}/quotes/preview",
        json={"selected_products": [{"product_id": "P01", "quantity": 1}]},
    )
    assert quote.status_code == 200

    updated_profile = _profile("Asha Trading House", "Mumbai")
    updated_profile["primary_requirements"] = ["connectivity", "security_iot"]
    updated = client.put(
        f"/api/v1/applicants/{applicant_id}", json=updated_profile
    )

    assert updated.status_code == 200
    assert updated.json()["applicant"]["applicant_id"] == applicant_id
    assert updated.json()["applicant"]["profile"]["business_name"] == "Asha Trading House"
    assert updated.json()["applicant"]["profile"]["city"] == "Mumbai"
    assert updated.json()["applicant"]["profile"]["primary_requirements"] == [
        "connectivity",
        "security_iot",
    ]
    assert updated.json()["applicant"]["latest_quote"] is None
    assert applicant_service.quote_preview_count(applicant_id) == 0
    assert kyc_service._read_manifest(applicant_id)["profile"] == {
        "business_name": "Asha Trading House",
        "business_address": "Mumbai",
    }


def test_unknown_applicant_cannot_receive_a_quote(monkeypatch, tmp_path) -> None:
    _configure_isolated_storage(monkeypatch, tmp_path)

    response = client.post(
        "/api/v1/applicants/APPL-0123456789abcdef0123456789abcdef/quotes/preview",
        json={"selected_products": [{"product_id": "P01", "quantity": 1}]},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Applicant was not found."


def test_applicant_rejects_gstin_status_that_disagrees_with_self_report(
    monkeypatch, tmp_path
) -> None:
    _configure_isolated_storage(monkeypatch, tmp_path)
    profile = _profile("Mismatch Traders", "Pune")
    profile["business_profile"]["gstin_verified"] = True

    response = client.post("/api/v1/applicants", json=profile)

    assert response.status_code == 422
    assert "must match the self-reported GSTIN status" in response.text
