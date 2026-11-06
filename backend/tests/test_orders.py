"""Phase 5 order lifecycle, authorization, and regression tests."""

import json
import os
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.security.kyc_auth import hash_password
from app.services import applicant_service, order_service

client = TestClient(app)

_customer_hash = hash_password("CustomerPass1234!")
_reviewer_hash = hash_password("ReviewerPass1234!")
_ops_hash = hash_password("OperationsPass1!")
_partner_hash = hash_password("PartnerPass12345!")
_partner2_hash = hash_password("Partner2Pass1234!")


def _make_users(applicant_ids: list[str]) -> str:
    return json.dumps([
        {"username": "cust1", "role": "CUSTOMER", "password_hash": _customer_hash,
         "applicant_ids": applicant_ids},
        {"username": "cust2", "role": "CUSTOMER", "password_hash": _customer_hash,
         "applicant_ids": ["APPL-ffffeeeeddddccccbbbbaaaa00001111"]},
        {"username": "reviewer1", "role": "REVIEWER", "password_hash": _reviewer_hash,
         "applicant_ids": []},
        {"username": "ops1", "role": "OPERATIONS", "password_hash": _ops_hash,
         "applicant_ids": []},
        {"username": "partner1", "role": "PARTNER", "password_hash": _partner_hash,
         "applicant_ids": []},
        {"username": "partner2", "role": "PARTNER", "password_hash": _partner2_hash,
         "applicant_ids": []},
    ])


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(applicant_service, "APPLICANT_DATABASE_PATH", db_path)
    monkeypatch.setattr(order_service, "APPLICANT_DATABASE_PATH", db_path)
    monkeypatch.setenv("UDYAMONE_KYC_AUTH_SECRET", "test-secret-for-phase5-orders-32bytes!")
    from app.services import kyc_service
    monkeypatch.setattr(kyc_service, "UPLOAD_ROOT", tmp_path / "uploads")
    return monkeypatch


def _create_applicant_with_quote() -> str:
    profile = {
        "business_name": "Test Co", "business_type": "Micro retail", "city": "Mumbai",
        "business_profile": {"city_tier": 1, "employee_count": 5, "site_count": 1, "gstin_verified": False},
        "business_segment": "micro", "gstin_self_reported_status": "Not registered",
        "primary_requirements": ["connectivity"],
    }
    r = client.post("/api/v1/applicants", json=profile)
    assert r.status_code == 201, r.text
    applicant_id = r.json()["applicant"]["applicant_id"]
    r2 = client.post(
        f"/api/v1/applicants/{applicant_id}/quotes/preview",
        json={"selected_products": [{"product_id": "P01", "quantity": 1}]},
    )
    assert r2.status_code == 200, r2.text
    return applicant_id


def _login(username: str, password: str) -> str:
    r = client.post("/api/v1/auth/session", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _setup_customer(monkeypatch, applicant_id: str) -> str:
    monkeypatch.setenv("UDYAMONE_KYC_AUTH_USERS", _make_users([applicant_id]))
    return _login("cust1", "CustomerPass1234!")


# ── Order creation ────────────────────────────────────────────────────────────

def test_customer_can_place_order(isolated_db):
    applicant_id = _create_applicant_with_quote()
    token = _setup_customer(isolated_db, applicant_id)
    r = client.post("/api/v1/orders",
                    json={"applicant_id": applicant_id, "confirmed": True},
                    headers=_auth(token))
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["status"] == "ORDER_PLACED"
    assert data["applicant_id"] == applicant_id
    assert data["snapshot"]["line_items"]
    assert "prototype order request" in data["snapshot"]["disclosure"]


def test_order_requires_confirmation(isolated_db):
    applicant_id = _create_applicant_with_quote()
    token = _setup_customer(isolated_db, applicant_id)
    r = client.post("/api/v1/orders",
                    json={"applicant_id": applicant_id, "confirmed": False},
                    headers=_auth(token))
    assert r.status_code == 422


def test_duplicate_order_rejected(isolated_db):
    applicant_id = _create_applicant_with_quote()
    token = _setup_customer(isolated_db, applicant_id)
    r1 = client.post("/api/v1/orders",
                     json={"applicant_id": applicant_id, "confirmed": True},
                     headers=_auth(token))
    assert r1.status_code == 201
    r2 = client.post("/api/v1/orders",
                     json={"applicant_id": applicant_id, "confirmed": True},
                     headers=_auth(token))
    assert r2.status_code == 409


def test_order_without_quote_rejected(isolated_db):
    profile = {
        "business_name": "No Quote Co", "business_type": "Micro retail", "city": "Delhi",
        "business_profile": {"city_tier": 1, "employee_count": 2, "site_count": 1, "gstin_verified": False},
        "business_segment": "micro", "gstin_self_reported_status": "Not registered",
        "primary_requirements": ["connectivity"],
    }
    r = client.post("/api/v1/applicants", json=profile)
    applicant_id = r.json()["applicant"]["applicant_id"]
    token = _setup_customer(isolated_db, applicant_id)
    r2 = client.post("/api/v1/orders",
                     json={"applicant_id": applicant_id, "confirmed": True},
                     headers=_auth(token))
    assert r2.status_code == 409


def test_customer_cannot_order_for_another_applicant(isolated_db):
    applicant_id = _create_applicant_with_quote()
    isolated_db.setenv("UDYAMONE_KYC_AUTH_USERS", _make_users([applicant_id]))
    token = _login("cust1", "CustomerPass1234!")
    other_id = _create_applicant_with_quote()
    r = client.post("/api/v1/orders",
                    json={"applicant_id": other_id, "confirmed": True},
                    headers=_auth(token))
    assert r.status_code == 403


# ── Snapshot immutability ─────────────────────────────────────────────────────

def test_snapshot_is_immutable_after_profile_update(isolated_db):
    applicant_id = _create_applicant_with_quote()
    token = _setup_customer(isolated_db, applicant_id)
    r = client.post("/api/v1/orders",
                    json={"applicant_id": applicant_id, "confirmed": True},
                    headers=_auth(token))
    assert r.status_code == 201
    original_snapshot = r.json()["snapshot"]
    order_id = r.json()["order_id"]

    profile = {
        "business_name": "Updated Co", "business_type": "Manufacturing", "city": "Chennai",
        "business_profile": {"city_tier": 2, "employee_count": 50, "site_count": 3, "gstin_verified": False},
        "business_segment": "mfg", "gstin_self_reported_status": "Not registered",
        "primary_requirements": ["connectivity"],
    }
    client.put(f"/api/v1/applicants/{applicant_id}", json=profile)

    isolated_db.setenv("UDYAMONE_KYC_AUTH_USERS", _make_users([applicant_id]))
    ops_token = _login("ops1", "OperationsPass1!")
    r2 = client.get(f"/api/v1/operations/orders/{order_id}", headers=_auth(ops_token))
    assert r2.status_code == 200
    assert r2.json()["snapshot"] == original_snapshot


# ── Customer order detail authorization ───────────────────────────────────────

def test_customer_can_retrieve_own_order(isolated_db):
    applicant_id = _create_applicant_with_quote()
    token = _setup_customer(isolated_db, applicant_id)
    order_id = _place_order(applicant_id, token)
    r = client.get(f"/api/v1/orders/{order_id}", headers=_auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["order_id"] == order_id
    assert r.json()["applicant_id"] == applicant_id


def test_customer_cannot_retrieve_another_applicants_order(isolated_db):
    applicant_id = _create_applicant_with_quote()
    token = _setup_customer(isolated_db, applicant_id)
    order_id = _place_order(applicant_id, token)

    isolated_db.setenv("UDYAMONE_KYC_AUTH_USERS",
                       _make_users(["APPL-ffffeeeeddddccccbbbbaaaa00001111"]))
    token2 = _login("cust2", "CustomerPass1234!")
    r = client.get(f"/api/v1/orders/{order_id}", headers=_auth(token2))
    assert r.status_code == 403


def test_reviewer_cannot_access_customer_order_endpoint(isolated_db):
    applicant_id = _create_applicant_with_quote()
    token = _setup_customer(isolated_db, applicant_id)
    order_id = _place_order(applicant_id, token)

    reviewer_token = _login("reviewer1", "ReviewerPass1234!")
    r = client.get(f"/api/v1/orders/{order_id}", headers=_auth(reviewer_token))
    assert r.status_code == 403


def test_operations_cannot_access_customer_order_endpoint(isolated_db):
    applicant_id = _create_applicant_with_quote()
    token = _setup_customer(isolated_db, applicant_id)
    order_id = _place_order(applicant_id, token)

    ops_token = _login("ops1", "OperationsPass1!")
    r = client.get(f"/api/v1/orders/{order_id}", headers=_auth(ops_token))
    assert r.status_code == 403


def test_partner_cannot_access_customer_order_endpoint(isolated_db):
    applicant_id = _create_applicant_with_quote()
    token = _setup_customer(isolated_db, applicant_id)
    order_id = _place_order(applicant_id, token)

    partner_token = _login("partner1", "PartnerPass12345!")
    r = client.get(f"/api/v1/orders/{order_id}", headers=_auth(partner_token))
    assert r.status_code == 403


# ── Lifecycle transitions ─────────────────────────────────────────────────────

def _place_order(applicant_id: str, token: str) -> str:
    r = client.post("/api/v1/orders",
                    json={"applicant_id": applicant_id, "confirmed": True},
                    headers=_auth(token))
    assert r.status_code == 201, r.text
    return r.json()["order_id"]


def test_operations_can_put_order_on_hold_and_resume(isolated_db):
    applicant_id = _create_applicant_with_quote()
    token = _setup_customer(isolated_db, applicant_id)
    order_id = _place_order(applicant_id, token)

    ops_token = _login("ops1", "OperationsPass1!")
    r = client.post(f"/api/v1/operations/orders/{order_id}/transition",
                    json={"to_status": "ON_HOLD", "reason": "Pending verification"},
                    headers=_auth(ops_token))
    assert r.status_code == 200
    assert r.json()["status"] == "ON_HOLD"

    r2 = client.post(f"/api/v1/operations/orders/{order_id}/transition",
                     json={"to_status": "ORDER_PLACED", "reason": "Verification complete"},
                     headers=_auth(ops_token))
    assert r2.status_code == 200
    assert r2.json()["status"] == "ORDER_PLACED"


def test_invalid_transition_rejected(isolated_db):
    applicant_id = _create_applicant_with_quote()
    token = _setup_customer(isolated_db, applicant_id)
    order_id = _place_order(applicant_id, token)

    ops_token = _login("ops1", "OperationsPass1!")
    r = client.post(f"/api/v1/operations/orders/{order_id}/transition",
                    json={"to_status": "ACTIVATED"},
                    headers=_auth(ops_token))
    assert r.status_code == 409


def test_full_lifecycle_order_placed_to_activated(isolated_db):
    applicant_id = _create_applicant_with_quote()
    token = _setup_customer(isolated_db, applicant_id)
    order_id = _place_order(applicant_id, token)

    ops_token = _login("ops1", "OperationsPass1!")
    partner_token = _login("partner1", "PartnerPass12345!")

    r = client.post(f"/api/v1/operations/orders/{order_id}/assign",
                    json={"partner_username": "partner1"},
                    headers=_auth(ops_token))
    assert r.status_code == 200
    assert r.json()["status"] == "ASSIGNED"

    r = client.post(f"/api/v1/partner/orders/{order_id}/transition",
                    json={"to_status": "FULFILMENT_IN_PROGRESS"},
                    headers=_auth(partner_token))
    assert r.status_code == 200

    r = client.post(f"/api/v1/partner/orders/{order_id}/transition",
                    json={"to_status": "FULFILMENT_COMPLETED"},
                    headers=_auth(partner_token))
    assert r.status_code == 200

    r = client.post(f"/api/v1/partner/orders/{order_id}/transition",
                    json={"to_status": "ACTIVATION_PENDING"},
                    headers=_auth(partner_token))
    assert r.status_code == 200

    r = client.post(f"/api/v1/operations/orders/{order_id}/transition",
                    json={"to_status": "ACTIVATED"},
                    headers=_auth(ops_token))
    assert r.status_code == 200
    assert r.json()["status"] == "ACTIVATED"

    statuses = [e["to_status"] for e in r.json()["events"]]
    assert "ORDER_PLACED" in statuses
    assert "ASSIGNED" in statuses
    assert "ACTIVATED" in statuses


def test_event_history_records_actor_and_timestamp(isolated_db):
    applicant_id = _create_applicant_with_quote()
    token = _setup_customer(isolated_db, applicant_id)
    order_id = _place_order(applicant_id, token)

    ops_token = _login("ops1", "OperationsPass1!")
    r = client.get(f"/api/v1/operations/orders/{order_id}", headers=_auth(ops_token))
    events = r.json()["events"]
    assert len(events) >= 1
    e = events[0]
    assert e["actor_username"] == "cust1"
    assert e["actor_role"] == "CUSTOMER"
    assert e["created_at"]


def test_cancelled_order_allows_new_order(isolated_db):
    applicant_id = _create_applicant_with_quote()
    token = _setup_customer(isolated_db, applicant_id)
    order_id = _place_order(applicant_id, token)

    r = client.post(f"/api/v1/orders/{order_id}/cancel", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["status"] == "CANCELLED"

    # New quote needed after profile update clears old quote
    r2 = client.post(
        f"/api/v1/applicants/{applicant_id}/quotes/preview",
        json={"selected_products": [{"product_id": "P01", "quantity": 1}]},
    )
    assert r2.status_code == 200

    r3 = client.post("/api/v1/orders",
                     json={"applicant_id": applicant_id, "confirmed": True},
                     headers=_auth(token))
    assert r3.status_code == 201


# ── Authorization ─────────────────────────────────────────────────────────────

def test_reviewer_cannot_access_operations_endpoints(isolated_db):
    isolated_db.setenv("UDYAMONE_KYC_AUTH_USERS", _make_users(["APPL-dummy00000000000000000000000001"]))
    reviewer_token = _login("reviewer1", "ReviewerPass1234!")
    r = client.get("/api/v1/operations/orders", headers=_auth(reviewer_token))
    assert r.status_code == 403


def test_partner_cannot_access_unassigned_order(isolated_db):
    applicant_id = _create_applicant_with_quote()
    token = _setup_customer(isolated_db, applicant_id)
    order_id = _place_order(applicant_id, token)

    partner_token = _login("partner1", "PartnerPass12345!")
    r = client.get(f"/api/v1/partner/orders/{order_id}", headers=_auth(partner_token))
    assert r.status_code == 403


def test_partner_cannot_access_another_partners_order(isolated_db):
    applicant_id = _create_applicant_with_quote()
    token = _setup_customer(isolated_db, applicant_id)
    order_id = _place_order(applicant_id, token)

    ops_token = _login("ops1", "OperationsPass1!")
    client.post(f"/api/v1/operations/orders/{order_id}/assign",
                json={"partner_username": "partner1"}, headers=_auth(ops_token))

    partner2_token = _login("partner2", "Partner2Pass1234!")
    r = client.get(f"/api/v1/partner/orders/{order_id}", headers=_auth(partner2_token))
    assert r.status_code == 403


def test_partner_cannot_reassign_orders(isolated_db):
    applicant_id = _create_applicant_with_quote()
    token = _setup_customer(isolated_db, applicant_id)
    order_id = _place_order(applicant_id, token)

    partner_token = _login("partner1", "PartnerPass12345!")
    r = client.post(f"/api/v1/operations/orders/{order_id}/assign",
                    json={"partner_username": "partner2"}, headers=_auth(partner_token))
    assert r.status_code == 403


def test_customer_can_cancel_own_order(isolated_db):
    applicant_id = _create_applicant_with_quote()
    token = _setup_customer(isolated_db, applicant_id)
    order_id = _place_order(applicant_id, token)

    r = client.post(f"/api/v1/orders/{order_id}/cancel", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["status"] == "CANCELLED"


def test_customer_cannot_cancel_another_customers_order(isolated_db):
    applicant_id = _create_applicant_with_quote()
    token = _setup_customer(isolated_db, applicant_id)
    order_id = _place_order(applicant_id, token)

    isolated_db.setenv("UDYAMONE_KYC_AUTH_USERS",
                       _make_users(["APPL-ffffeeeeddddccccbbbbaaaa00001111"]))
    token2 = _login("cust2", "CustomerPass1234!")
    r = client.post(f"/api/v1/orders/{order_id}/cancel", headers=_auth(token2))
    assert r.status_code == 403


def test_operations_can_list_and_filter_orders(isolated_db):
    applicant_id = _create_applicant_with_quote()
    token = _setup_customer(isolated_db, applicant_id)
    _place_order(applicant_id, token)

    ops_token = _login("ops1", "OperationsPass1!")
    r = client.get("/api/v1/operations/orders", headers=_auth(ops_token))
    assert r.status_code == 200
    assert len(r.json()) >= 1

    r2 = client.get("/api/v1/operations/orders?status=ORDER_PLACED", headers=_auth(ops_token))
    assert r2.status_code == 200
    assert all(o["status"] == "ORDER_PLACED" for o in r2.json())


def test_partner_list_only_shows_assigned_orders(isolated_db):
    applicant_id = _create_applicant_with_quote()
    token = _setup_customer(isolated_db, applicant_id)
    order_id = _place_order(applicant_id, token)

    partner_token = _login("partner1", "PartnerPass12345!")
    r_before = client.get("/api/v1/partner/orders", headers=_auth(partner_token))
    assert r_before.json() == []

    ops_token = _login("ops1", "OperationsPass1!")
    client.post(f"/api/v1/operations/orders/{order_id}/assign",
                json={"partner_username": "partner1"}, headers=_auth(ops_token))

    r_after = client.get("/api/v1/partner/orders", headers=_auth(partner_token))
    assert len(r_after.json()) == 1
    assert r_after.json()[0]["order_id"] == order_id


def test_customer_order_list(isolated_db):
    applicant_id = _create_applicant_with_quote()
    token = _setup_customer(isolated_db, applicant_id)
    _place_order(applicant_id, token)

    r = client.get(f"/api/v1/orders/applicant/{applicant_id}", headers=_auth(token))
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_customer_cannot_list_another_applicants_orders(isolated_db):
    applicant_id = _create_applicant_with_quote()
    token = _setup_customer(isolated_db, applicant_id)

    other_id = _create_applicant_with_quote()
    r = client.get(f"/api/v1/orders/applicant/{other_id}", headers=_auth(token))
    assert r.status_code == 403


# ── Regression ────────────────────────────────────────────────────────────────

def test_health_endpoint_regression():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_recommendations_regression():
    r = client.post("/api/v1/recommendations", json={
        "business_profile": {"city_tier": 1, "employee_count": 5, "site_count": 1, "gstin_verified": False},
        "business_segment": "micro",
        "primary_requirements": ["connectivity"],
    })
    assert r.status_code == 200
    assert "bundles" in r.json()


def test_kyc_auth_regression(isolated_db):
    isolated_db.setenv("UDYAMONE_KYC_AUTH_USERS", _make_users(["APPL-dummy00000000000000000000000001"]))
    r = client.post("/api/v1/auth/session",
                    json={"username": "reviewer1", "password": "ReviewerPass1234!"})
    assert r.status_code == 200
    assert r.json()["role"] == "REVIEWER"


def test_applicant_journey_regression():
    profile = {
        "business_name": "Regression Co", "business_type": "Micro retail", "city": "Pune",
        "business_profile": {"city_tier": 1, "employee_count": 3, "site_count": 1, "gstin_verified": False},
        "business_segment": "micro", "gstin_self_reported_status": "Not registered",
        "primary_requirements": ["connectivity"],
    }
    r = client.post("/api/v1/applicants", json=profile)
    assert r.status_code == 201
    applicant_id = r.json()["applicant"]["applicant_id"]
    r2 = client.get(f"/api/v1/applicants/{applicant_id}")
    assert r2.status_code == 200
    assert r2.json()["applicant_id"] == applicant_id
