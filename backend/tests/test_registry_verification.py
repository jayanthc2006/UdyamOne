"""Synthetic registry matching, persistence, and authenticated workflow tests."""

import csv
import re
from io import BytesIO
from pathlib import Path
import unicodedata

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.models.recommendation import RecommendationRequest
from app.models.verification import RegistryVerificationStatus
from app.security.kyc_auth import (
    create_session_token,
    hash_password,
    load_kyc_auth_configuration,
)
from app.services import applicant_service, kyc_service, registry_verification_service

client = TestClient(app)
_GST_COLUMNS = [
    "gstin",
    "legal_name",
    "trade_name",
    "constitution",
    "principal_place_of_business",
    "state",
    "registration_date",
    "status",
]
_UDYAM_COLUMNS = [
    "udyam_number",
    "enterprise_name",
    "enterprise_type",
    "major_activity",
    "nic_description",
    "state",
    "city",
    "date_of_registration",
]


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _normalized_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"[a-z0-9]+", value))


def _matching_registry_pair() -> tuple[dict[str, str], dict[str, str]]:
    udyam_by_name: dict[str, list[dict[str, str]]] = {}
    for row in _read_rows(registry_verification_service.UDYAM_REGISTRY_PATH):
        udyam_by_name.setdefault(
            _normalized_text(row["enterprise_name"]), []
        ).append(row)

    for gst_row in _read_rows(registry_verification_service.GSTIN_REGISTRY_PATH):
        if gst_row["status"].casefold() != "active":
            continue
        matches = udyam_by_name.get(_normalized_text(gst_row["legal_name"]), [])
        for udyam_row in matches:
            if (
                _normalized_text(udyam_row["city"])
                in _normalized_text(gst_row["principal_place_of_business"])
            ):
                return gst_row, udyam_row
    raise AssertionError("The supplied registries contain no cross-registry test pair.")


def _document_values(
    gst_row: dict[str, str],
    udyam_row: dict[str, str],
) -> dict[str, str]:
    return {
        "gstin": gst_row["gstin"],
        "gst_legal_name": gst_row["legal_name"],
        "gst_trade_name": gst_row["trade_name"],
        "gst_registered_address": gst_row["principal_place_of_business"],
        "udyam_number": udyam_row["udyam_number"],
        "udyam_enterprise_name": udyam_row["enterprise_name"],
    }


def _write_registry(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _png_bytes() -> bytes:
    image = Image.new("RGB", (850, 300), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_gstin_and_udyam_matching_normalization_and_field_conflicts(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(
        applicant_service, "APPLICANT_DATABASE_PATH", tmp_path / "applicants.sqlite3"
    )
    gst_row, udyam_row = _matching_registry_pair()
    values = _document_values(gst_row, udyam_row)

    verified = registry_verification_service.verify_applicant_registries(
        "APPL-test",
        gst_row["legal_name"],
        udyam_row["city"],
        {
            **values,
            "gstin": gst_row["gstin"].lower(),
            "udyam_number": re.sub(r"[-/ ]", "", udyam_row["udyam_number"].lower()),
        },
    )

    assert verified["GSTIN"].status is RegistryVerificationStatus.VERIFIED
    assert verified["UDYAM"].status is RegistryVerificationStatus.VERIFIED
    assert "applicant_business_name" in verified["GSTIN"].compared_fields
    assert "city" in verified["UDYAM"].compared_fields

    gst_mismatch = registry_verification_service._verify_gstin(
        values["gstin"],
        "Unrelated Business",
        values,
    )
    udyam_mismatch = registry_verification_service._verify_udyam(
        values["udyam_number"],
        values["udyam_enterprise_name"],
        "Unrelated City",
        values,
    )
    assert gst_mismatch.status is RegistryVerificationStatus.MISMATCH
    assert "applicant_business_name" in gst_mismatch.mismatched_fields
    assert udyam_mismatch.status is RegistryVerificationStatus.MISMATCH
    assert "city" in udyam_mismatch.mismatched_fields


def test_missing_invalid_and_unmatched_identifiers_are_inconclusive(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(
        applicant_service, "APPLICANT_DATABASE_PATH", tmp_path / "applicants.sqlite3"
    )
    _, udyam_row = _matching_registry_pair()
    gstin_missing = registry_verification_service._verify_gstin(
        None, "A Business", {}
    )
    gstin_invalid = registry_verification_service._verify_gstin(
        "not-a-gstin", "A Business", {}
    )
    gstin_unmatched = registry_verification_service._verify_gstin(
        "99ABCDE1234F1Z5", "A Business", {}
    )
    udyam_unmatched = registry_verification_service._verify_udyam(
        "UDYAMZZ009999999",
        "A Business",
        "Unknown City",
        {},
    )

    assert gstin_missing.status is RegistryVerificationStatus.INCONCLUSIVE
    assert gstin_invalid.status is RegistryVerificationStatus.INCONCLUSIVE
    assert gstin_unmatched.status is RegistryVerificationStatus.INCONCLUSIVE
    assert udyam_unmatched.status is RegistryVerificationStatus.INCONCLUSIVE


def test_registry_duplicates_and_unavailable_or_malformed_files(
    monkeypatch, tmp_path
) -> None:
    gst_row, udyam_row = _matching_registry_pair()
    values = _document_values(gst_row, udyam_row)
    gst_file = tmp_path / "gst.csv"
    _write_registry(
        gst_file,
        _GST_COLUMNS,
        [gst_row, {**gst_row, "legal_name": f"{gst_row['legal_name']} Different"}],
    )
    monkeypatch.setattr(registry_verification_service, "GSTIN_REGISTRY_PATH", gst_file)
    conflict = registry_verification_service._verify_gstin(
        values["gstin"],
        gst_row["legal_name"],
        values,
    )
    assert conflict.status is RegistryVerificationStatus.INCONCLUSIVE

    missing_file = tmp_path / "missing.csv"
    monkeypatch.setattr(registry_verification_service, "GSTIN_REGISTRY_PATH", missing_file)
    monkeypatch.setattr(
        applicant_service, "APPLICANT_DATABASE_PATH", tmp_path / "unavailable.sqlite3"
    )
    unavailable = registry_verification_service.verify_applicant_registries(
        "APPL-unavailable", gst_row["legal_name"], udyam_row["city"], values
    )["GSTIN"]
    assert unavailable.status is RegistryVerificationStatus.UNAVAILABLE

    _write_registry(missing_file, ["wrong_header"], [{"wrong_header": "value"}])
    malformed = registry_verification_service.verify_applicant_registries(
        "APPL-malformed", gst_row["legal_name"], udyam_row["city"], values
    )["GSTIN"]
    assert malformed.status is RegistryVerificationStatus.UNAVAILABLE

    udyam_file = tmp_path / "udyam.csv"
    _write_registry(
        udyam_file,
        _UDYAM_COLUMNS,
        [
            udyam_row,
            {**udyam_row, "city": f"{udyam_row['city']} Different"},
        ],
    )
    monkeypatch.setattr(
        registry_verification_service, "UDYAM_REGISTRY_PATH", udyam_file
    )
    udyam_duplicate = registry_verification_service._verify_udyam(
        values["udyam_number"],
        udyam_row["enterprise_name"],
        udyam_row["city"],
        values,
    )
    assert udyam_duplicate.status is RegistryVerificationStatus.INCONCLUSIVE


def test_verification_metadata_persists_per_applicant_and_stales_on_input_change(
    monkeypatch, tmp_path
) -> None:
    database_path = tmp_path / "applicants.sqlite3"
    monkeypatch.setattr(
        applicant_service, "APPLICANT_DATABASE_PATH", database_path
    )
    gst_row, udyam_row = _matching_registry_pair()
    values = _document_values(gst_row, udyam_row)
    result = registry_verification_service.verify_applicant_registries(
        "APPL-one", gst_row["legal_name"], udyam_row["city"], values
    )
    persisted = registry_verification_service.get_persisted_verifications(
        "APPL-one", gst_row["legal_name"], udyam_row["city"], values
    )
    isolated = registry_verification_service.get_persisted_verifications(
        "APPL-two", gst_row["legal_name"], udyam_row["city"], values
    )
    stale = registry_verification_service.get_persisted_verifications(
        "APPL-one", "Changed Business", udyam_row["city"], values
    )

    assert result["GSTIN"].status is RegistryVerificationStatus.VERIFIED
    assert persisted["GSTIN"] == result["GSTIN"]
    assert isolated == {"GSTIN": None, "UDYAM": None}
    assert stale["GSTIN"] is None

    with database_path.open("rb") as file:
        content = file.read()
    assert gst_row["gstin"].encode() not in content
    assert gst_row["legal_name"].encode() not in content


def test_customer_registry_endpoint_respects_consent_roles_and_persisted_eligibility(
    monkeypatch, tmp_path
) -> None:
    database_path = tmp_path / "applicants.sqlite3"
    uploads = tmp_path / "uploads"
    monkeypatch.setattr(applicant_service, "APPLICANT_DATABASE_PATH", database_path)
    monkeypatch.setattr(kyc_service, "UPLOAD_ROOT", uploads)
    monkeypatch.delenv("UDYAMONE_KYC_REQUIRED_DOCUMENTS", raising=False)
    monkeypatch.setattr(applicant_service, "_new_applicant_id", lambda: "APPL-" + "a" * 32)
    gst_row, udyam_row = _matching_registry_pair()
    profile = {
        "business_name": gst_row["legal_name"],
        "business_type": "Manufacturing",
        "city": udyam_row["city"],
        "business_profile": {
            "city_tier": 1,
            "employee_count": 25,
            "site_count": 1,
            "gstin_verified": True,
        },
        "business_segment": "mfg",
        "gstin_self_reported_status": "Verified",
        "primary_requirements": ["connectivity"],
    }
    created = client.post("/api/v1/applicants", json=profile)
    assert created.status_code == 201
    applicant_id = created.json()["applicant"]["applicant_id"]
    initial_products = {
        product["product_id"]
        for bundle in created.json()["recommendations"]["bundles"]
        for product in bundle["products"]
    }
    assert "P03" not in initial_products

    customer_hash = hash_password("SyntheticCustomerPassword1!")
    other_hash = hash_password("SyntheticOtherPassword1!")
    reviewer_hash = hash_password("SyntheticReviewerPassword1!")
    monkeypatch.setenv(
        "UDYAMONE_KYC_AUTH_SECRET", "synthetic-registry-test-secret-0123456789"
    )
    monkeypatch.setenv(
        "UDYAMONE_KYC_AUTH_USERS",
        (
            '[{"username":"customer-a","role":"CUSTOMER",'
            f'"password_hash":"{customer_hash}","applicant_ids":["{applicant_id}"]}},'
            '{"username":"customer-b","role":"CUSTOMER",'
            f'"password_hash":"{other_hash}","applicant_ids":["APPL-other"]}},'
            '{"username":"reviewer","role":"REVIEWER",'
            f'"password_hash":"{reviewer_hash}","applicant_ids":[]}}]'
        ),
    )
    configuration = load_kyc_auth_configuration()
    customer_token, _ = create_session_token(
        configuration.accounts["customer-a"], configuration.secret
    )
    other_token, _ = create_session_token(
        configuration.accounts["customer-b"], configuration.secret
    )
    reviewer_token, _ = create_session_token(
        configuration.accounts["reviewer"], configuration.secret
    )
    customer_headers = {"Authorization": f"Bearer {customer_token}"}

    no_consent = client.post(
        f"/api/v1/kyc/{applicant_id}/verify-registries",
        headers=customer_headers,
    )
    consent = client.post(
        f"/api/v1/kyc/{applicant_id}/consent",
        json={"consented": True},
        headers=customer_headers,
    )
    assert no_consent.status_code == 409
    assert consent.status_code == 200
    assert consent.json()["consent"]["consent_version"] == "kyc-consent-v2"
    self_asserted_quote = client.post(
        f"/api/v1/applicants/{applicant_id}/quotes/preview",
        json={"selected_products": [{"product_id": "P03", "quantity": 1}]},
    )
    assert self_asserted_quote.status_code == 422

    cross_applicant = client.post(
        f"/api/v1/kyc/{applicant_id}/verify-registries",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    reviewer_check = client.post(
        f"/api/v1/kyc/{applicant_id}/verify-registries",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert cross_applicant.status_code == 403
    assert reviewer_check.status_code == 403

    gst_text = (
        f"GSTIN: {gst_row['gstin']}\n"
        f"Legal Name of Business: {gst_row['legal_name']}\n"
        f"Trade Name: {gst_row['trade_name']}\n"
        f"Principal Place of Business: {gst_row['principal_place_of_business']}"
    )
    udyam_text = (
        f"Udyam Registration Number: {udyam_row['udyam_number']}\n"
        f"Name of Enterprise: {udyam_row['enterprise_name']}"
    )
    ocr_responses = iter((gst_text, udyam_text))
    monkeypatch.setattr(
        kyc_service,
        "_run_windows_ocr",
        lambda paths: [
            {"status": "SUCCEEDED", "text": next(ocr_responses), "confidence": None}
            for _ in paths
        ],
    )
    for document_type in ("gst_certificate", "udyam_certificate"):
        uploaded = client.put(
            f"/api/v1/kyc/{applicant_id}/documents/{document_type}",
            content=_png_bytes(),
            headers={**customer_headers, "content-type": "image/png"},
        )
        assert uploaded.status_code == 200
        processed = client.post(
            f"/api/v1/kyc/{applicant_id}/documents/{document_type}/process",
            headers=customer_headers,
        )
        assert processed.status_code == 200

    checked = client.post(
        f"/api/v1/kyc/{applicant_id}/verify-registries",
        headers=customer_headers,
    )
    assert checked.status_code == 200
    assert checked.json()["gstin_verification"]["status"] == "VERIFIED"
    assert checked.json()["udyam_verification"]["status"] == "VERIFIED"
    assert checked.json()["required_registry_verifications"] == ["GSTIN", "UDYAM"]
    assert next(
        document
        for document in checked.json()["documents"]
        if document["document_type"] == "gst_certificate"
    )["validation"] == "NOT_REVIEWED"
    assert next(
        document
        for document in checked.json()["documents"]
        if document["document_type"] == "gst_certificate"
    )["registry_verification"] == "VERIFIED"
    verified_quote = client.post(
        f"/api/v1/applicants/{applicant_id}/quotes/preview",
        json={"selected_products": [{"product_id": "P03", "quantity": 1}]},
    )
    assert verified_quote.status_code == 200

    refreshed = client.get(
        f"/api/v1/kyc/{applicant_id}",
        headers=customer_headers,
    )
    assert refreshed.json()["gstin_verification"]["status"] == "VERIFIED"
    reviewer_valid_gst = client.post(
        f"/api/v1/kyc/{applicant_id}/documents/gst_certificate/review",
        json={"validation": "VALID"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    reviewer_valid_udyam = client.post(
        f"/api/v1/kyc/{applicant_id}/documents/udyam_certificate/review",
        json={"validation": "VALID"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert reviewer_valid_gst.status_code == reviewer_valid_udyam.status_code == 200
    assert reviewer_valid_udyam.json()["ready_for_approval"] is True

    applicant_after_verification = client.get(
        f"/api/v1/applicants/{applicant_id}"
    ).json()
    updated_products = {
        product["product_id"]
        for bundle in applicant_after_verification["recommendations"]["bundles"]
        for product in bundle["products"]
    }
    assert "P03" in updated_products

    applicant_quote = client.post(
        f"/api/v1/applicants/{applicant_id}/quotes/preview",
        json={"selected_products": [{"product_id": "P03", "quantity": 1}]},
    )
    direct_quote = client.post(
        "/api/v1/quotes/preview",
        json={
            "business_profile": profile["business_profile"],
            "selected_products": [{"product_id": "P03", "quantity": 1}],
        },
    )
    assert applicant_quote.status_code == 200
    assert direct_quote.status_code == 422


def test_public_recommendations_cannot_assert_client_gstin_verification() -> None:
    request = RecommendationRequest(
        business_profile={
            "city_tier": 1,
            "employee_count": 5,
            "site_count": 1,
            "gstin_verified": True,
        },
        business_segment="micro",
        primary_requirements=["connectivity"],
    )
    recommendation_response = client.post(
        "/api/v1/recommendations",
        json=request.model_dump(mode="json"),
    )
    direct_eligibility = client.post(
        "/api/v1/eligibility/check",
        json={
            "business_profile": request.business_profile.model_dump(mode="json"),
            "selected_product_ids": ["P03"],
        },
    )

    assert recommendation_response.status_code == 200
    recommended_ids = {
        product["product_id"]
        for bundle in recommendation_response.json()["bundles"]
        for product in bundle["products"]
    }
    assert "P03" not in recommended_ids
    assert direct_eligibility.status_code == 200
    assert direct_eligibility.json()["results"][0]["is_eligible"] is False
