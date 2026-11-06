"""Authentication, consent, and role-bound KYC API tests."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.security.kyc_auth import (
    KycAuthConfigurationError,
    create_session_token,
    decode_session_token,
    hash_password,
    load_kyc_auth_configuration,
)
from app.services import kyc_service

client = TestClient(app)
_customer_password_hash = hash_password("SyntheticCustomerPassword1!")
_other_customer_password_hash = hash_password("SyntheticOtherPassword1!")
_reviewer_password_hash = hash_password("SyntheticReviewerPassword1!")


@pytest.fixture(autouse=True)
def configure_auth(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("UDYAMONE_KYC_AUTH_SECRET", "synthetic-test-signing-secret-not-for-use")
    monkeypatch.setenv(
        "UDYAMONE_KYC_AUTH_USERS",
        (
            '[{"username":"customer-a","role":"CUSTOMER",'
            f'"password_hash":"{_customer_password_hash}","applicant_ids":["APPL-A"]}},'
            '{"username":"customer-b","role":"CUSTOMER",'
            f'"password_hash":"{_other_customer_password_hash}","applicant_ids":["APPL-B"]}},'
            '{"username":"reviewer","role":"REVIEWER",'
            f'"password_hash":"{_reviewer_password_hash}","applicant_ids":[]}}]'
        ),
    )
    monkeypatch.setattr(kyc_service, "UPLOAD_ROOT", tmp_path)


def _login(username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/session",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _png_bytes() -> bytes:
    image = Image.new("RGB", (64, 64), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_missing_auth_configuration_fails_closed(monkeypatch) -> None:
    monkeypatch.delenv("UDYAMONE_KYC_AUTH_SECRET", raising=False)
    monkeypatch.delenv("UDYAMONE_KYC_AUTH_USERS", raising=False)

    login = client.post(
        "/api/v1/auth/session",
        json={"username": "reviewer", "password": "SyntheticReviewerPassword1!"},
    )
    assessment = client.get("/api/v1/kyc/K05")

    assert login.status_code == 503
    assert assessment.status_code == 503


def test_login_issues_server_configured_role_and_rejects_bad_password() -> None:
    login = client.post(
        "/api/v1/auth/session",
        json={"username": "reviewer", "password": "SyntheticReviewerPassword1!"},
    )
    invalid = client.post(
        "/api/v1/auth/session",
        json={"username": "reviewer", "password": "wrong-password"},
    )

    assert login.status_code == 200
    assert login.json()["role"] == "REVIEWER"
    assert login.json()["token_type"] == "bearer"
    assert login.json()["expires_in"] <= 1_800
    assert invalid.status_code == 401


def test_unauthenticated_access_and_customer_applicant_isolation() -> None:
    unauthenticated = client.get("/api/v1/kyc/APPL-A")
    customer_token = _login("customer-a", "SyntheticCustomerPassword1!")
    allowed = client.get(
        "/api/v1/kyc/APPL-A",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    denied = client.get(
        "/api/v1/kyc/APPL-B",
        headers={"Authorization": f"Bearer {customer_token}"},
    )

    assert unauthenticated.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json()["applicant_id"] == "APPL-A"
    assert denied.status_code == 403


def test_customer_cannot_review_and_reviewer_cannot_upload_or_process() -> None:
    customer_token = _login("customer-a", "SyntheticCustomerPassword1!")
    reviewer_token = _login("reviewer", "SyntheticReviewerPassword1!")
    customer_review = client.post(
        "/api/v1/kyc/APPL-A/documents/gst_certificate/review",
        json={"validation": "VALID"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    reviewer_upload = client.put(
        "/api/v1/kyc/APPL-A/documents/gst_certificate",
        content=_png_bytes(),
        headers={
            "Authorization": f"Bearer {reviewer_token}",
            "content-type": "image/png",
        },
    )
    reviewer_process = client.post(
        "/api/v1/kyc/APPL-A/documents/gst_certificate/process",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )

    assert customer_review.status_code == 403
    assert reviewer_upload.status_code == 403
    assert reviewer_process.status_code == 403


def test_consent_is_persisted_and_upload_and_ocr_are_blocked_after_decline() -> None:
    customer_token = _login("customer-a", "SyntheticCustomerPassword1!")
    headers = {"Authorization": f"Bearer {customer_token}"}
    document_url = "/api/v1/kyc/APPL-A/documents/gst_certificate"
    blocked_upload = client.put(
        document_url,
        content=_png_bytes(),
        headers={**headers, "content-type": "image/png"},
    )
    consent = client.post(
        "/api/v1/kyc/APPL-A/consent",
        json={"consented": True},
        headers=headers,
    )
    uploaded = client.put(
        document_url,
        content=_png_bytes(),
        headers={**headers, "content-type": "image/png"},
    )
    withdrawn = client.post(
        "/api/v1/kyc/APPL-A/consent",
        json={"consented": False},
        headers=headers,
    )
    blocked_processing = client.post(
        f"{document_url}/process",
        headers=headers,
    )

    assert blocked_upload.status_code == 409
    assert consent.status_code == 200
    consent_state = consent.json()["consent"]
    assert consent_state["applicant_id"] == "APPL-A"
    assert consent_state["consented"] is True
    assert consent_state["consent_version"] == "kyc-consent-v2"
    assert consent_state["timestamp"]
    assert uploaded.status_code == 200
    assert withdrawn.status_code == 200
    assert withdrawn.json()["consent"]["consented"] is False
    assert blocked_processing.status_code == 409


def test_customer_documents_are_isolated_and_reviewer_can_inspect() -> None:
    customer_a_token = _login("customer-a", "SyntheticCustomerPassword1!")
    customer_b_token = _login("customer-b", "SyntheticOtherPassword1!")
    reviewer_token = _login("reviewer", "SyntheticReviewerPassword1!")
    customer_a_headers = {"Authorization": f"Bearer {customer_a_token}"}
    customer_b_headers = {"Authorization": f"Bearer {customer_b_token}"}
    reviewer_headers = {"Authorization": f"Bearer {reviewer_token}"}
    consent = client.post(
        "/api/v1/kyc/APPL-A/consent",
        json={"consented": True},
        headers=customer_a_headers,
    )
    uploaded = client.put(
        "/api/v1/kyc/APPL-A/documents/address_proof",
        content=_png_bytes(),
        headers={**customer_a_headers, "content-type": "image/png"},
    )
    customer_a_denied = client.get(
        "/api/v1/kyc/APPL-B",
        headers=customer_a_headers,
    )
    customer_b_assessment = client.get(
        "/api/v1/kyc/APPL-B",
        headers=customer_b_headers,
    )
    reviewer_assessment = client.get(
        "/api/v1/kyc/APPL-A",
        headers=reviewer_headers,
    )

    assert consent.status_code == uploaded.status_code == 200
    assert customer_a_denied.status_code == 403
    assert customer_b_assessment.status_code == 200
    assert all(
        document["presence"] == "NOT_PROVIDED"
        for document in customer_b_assessment.json()["documents"]
    )
    assert reviewer_assessment.status_code == 200
    address_proof = next(
        document for document in reviewer_assessment.json()["documents"]
        if document["document_type"] == "address_proof"
    )
    assert address_proof["presence"] == "PROVIDED"


def test_reviewer_document_requests_are_persisted_and_block_readiness() -> None:
    reviewer_token = _login("reviewer", "SyntheticReviewerPassword1!")
    headers = {"Authorization": f"Bearer {reviewer_token}"}
    request = client.post(
        "/api/v1/kyc/APPL-A/additional-documents",
        json={"document_types": ["udyam_certificate"]},
        headers=headers,
    )
    refreshed = client.get("/api/v1/kyc/APPL-A", headers=headers)
    duplicate = client.post(
        "/api/v1/kyc/APPL-A/additional-documents",
        json={"document_types": ["udyam_certificate", "udyam_certificate"]},
        headers=headers,
    )

    assert request.status_code == 200
    assert request.json()["requested_documents"] == ["udyam_certificate"]
    assert request.json()["upload_requests"] == ["udyam_certificate"]
    assert request.json()["ready_for_approval"] is False
    assert refreshed.json()["requested_documents"] == ["udyam_certificate"]
    assert duplicate.status_code == 422


def test_expired_and_malformed_sessions_are_rejected(monkeypatch) -> None:
    configuration = load_kyc_auth_configuration()
    reviewer = configuration.accounts["reviewer"]
    expired, _ = create_session_token(
        reviewer,
        configuration.secret,
        now=100,
        lifetime_seconds=1,
    )
    with pytest.raises(ValueError, match="invalid or expired"):
        decode_session_token(expired, configuration, now=102)
    with pytest.raises(ValueError, match="invalid or expired"):
        decode_session_token("v1.%%%invalid", configuration)


def test_malformed_password_hash_configuration_fails_closed(monkeypatch) -> None:
    monkeypatch.setenv("UDYAMONE_KYC_AUTH_USERS", '[{"username":"bad","role":"CUSTOMER","password_hash":"%%%","applicant_ids":["APPL-A"]},{"username":"reviewer","role":"REVIEWER","password_hash":"%%%","applicant_ids":[]}]')

    with pytest.raises(KycAuthConfigurationError):
        load_kyc_auth_configuration()
