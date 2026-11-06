"""Quick API-level e2e of the QA backend: full lifecycle incl. partner + activation.
Run:  .\\.venv\\Scripts\\python.exe scripts\\qa_api_e2e.py
Prints PASS/FAIL per step. Uses ONLY the isolated QA backend on :8901.
"""
import json
import urllib.request

BASE = "http://127.0.0.1:8901"
RESULTS: list[tuple[str, str, str]] = []


def call(method: str, path: str, token: str | None = None, body: dict | None = None):
    req = urllib.request.Request(BASE + path, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data, timeout=15) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"null")
        except Exception:
            return e.code, {}


def check(name: str, ok: bool, extra: str = ""):
    RESULTS.append((name, "PASS" if ok else "FAIL", extra))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {extra}")


def login(u: str, p: str) -> str:
    status, data = call("POST", "/api/v1/auth/session", body={"username": u, "password": p})
    assert status == 200, (status, data)
    return data["access_token"]


# ---- Seed applicant (fresh, isolated DB) ----
status, seed = call("POST", "/qa/seed", body={"business_name": "E2E API Co"})
check("seed applicant with quote", status == 200 and "applicant_id" in seed, str(seed)[:120])
applicant_id = seed["applicant_id"]

cust = login("qa_cust", "CustomerQaPass123!")
ops = login("qa_ops", "OpsQaPass123456!")
partner = login("qa_partner", "PartnerQaPass123!")
reviewer = login("qa_reviewer", "ReviewerQaPass123!")
check("login all four roles", True)

# ---- Customer order placement ----
status, order = call("POST", "/api/v1/orders", cust,
                     {"applicant_id": applicant_id, "confirmed": True})
check("customer places order", status == 201, str(status))
order_id = order["order_id"]

status, dup = call("POST", "/api/v1/orders", cust,
                   {"applicant_id": applicant_id, "confirmed": True})
check("duplicate order rejected 409", status == 409, str(status))

status, detail = call("GET", f"/api/v1/orders/{order_id}", cust)
check("customer sees own order + snapshot",
      status == 200 and detail.get("snapshot", {}).get("line_items"))
status, _ = call("GET", f"/api/v1/orders/{order_id}", reviewer)
check("reviewer blocked from customer order detail (403)", status == 403, str(status))
status, _ = call("GET", f"/api/v1/orders/{order_id}", ops)
check("operations blocked from customer order detail (403)", status == 403, str(status))
status, _ = call("GET", f"/api/v1/orders/{order_id}", partner)
check("partner blocked from customer order detail (403)", status == 403, str(status))
status, _ = call("GET", f"/api/v1/orders/{order_id}")
check("unauthenticated blocked (401)", status == 401, str(status))

# ---- Operations: invalid transition, assignment, reassignment ----
status, _ = call("POST", f"/api/v1/operations/orders/{order_id}/transition", ops,
                 {"to_status": "ACTIVATED"})
check("invalid transition rejected 409", status == 409, str(status))

status, r = call("POST", f"/api/v1/operations/orders/{order_id}/assign", ops,
                 {"partner_username": "qa_partner", "reason": "Zone coverage"})
check("operations assigns partner", status == 200 and r.get("status") == "ASSIGNED")
status, r = call("POST", f"/api/v1/operations/orders/{order_id}/assign", cust,
                 {"partner_username": "qa_partner"})
check("customer cannot assign (403)", status == 403, str(status))
status, r = call("POST", f"/api/v1/operations/orders/{order_id}/assign", ops,
                 {"partner_username": "qa_ops"})
check("assigning non-partner role rejected", status in (400, 403, 409, 422), str(status))

status, r = call("GET", f"/api/v1/operations/orders/{order_id}", ops)
check("operations sees detail via operations endpoint",
      status == 200 and r.get("snapshot", {}).get("line_items"))
status, r = call("GET", "/api/v1/operations/orders?status=ASSIGNED", ops)
check("operations list+filter works", status == 200 and any(
    o.get("order_id") == order_id for o in r))

# ---- Partner fulfilment ----
status, _ = call("POST", f"/api/v1/partner/orders/{order_id}/transition", partner,
                 {"to_status": "FULFILMENT_IN_PROGRESS", "detail": "Site survey booked"})
check("partner starts fulfilment", status == 200)
status, r = call("GET", "/api/v1/partner/orders", partner)
check("partner lists assigned orders", status == 200 and any(
    o.get("order_id") == order_id for o in r))
status, r = call("GET", "/api/v1/partner/orders", partner)
# partner cannot transition to ACTIVATED directly
status, _ = call("POST", f"/api/v1/partner/orders/{order_id}/transition", partner,
                 {"to_status": "ACTIVATED"})
check("partner cannot activate (409/403)", status in (403, 409), str(status))
# partner cannot assign
status, _ = call("POST", f"/api/v1/operations/orders/{order_id}/assign", partner,
                 {"partner_username": "qa_partner"})
check("partner cannot assign (403)", status == 403, str(status))

# hold and resume
status, _ = call("POST", f"/api/v1/partner/orders/{order_id}/transition", partner,
                 {"to_status": "ON_HOLD", "reason": "Wayleave pending"})
check("partner puts order ON_HOLD", status == 200)
status, _ = call("POST", f"/api/v1/partner/orders/{order_id}/transition", partner,
                 {"to_status": "FULFILMENT_IN_PROGRESS"})
# Partner role is not in TRANSITION_ROLES for the hold→resume edge, so it is
# rejected regardless of whether state (409) or role (403) is checked first.
check("partner cannot resume from hold", status in (403, 409), str(status))
status, _ = call("POST", f"/api/v1/operations/orders/{order_id}/transition", ops,
                 {"to_status": "FULFILMENT_IN_PROGRESS", "reason": "Wayleave cleared"})
check("operations resumes from hold", status == 200)

status, _ = call("POST", f"/api/v1/partner/orders/{order_id}/transition", partner,
                 {"to_status": "FULFILMENT_COMPLETED", "detail": "Install complete"})
check("partner completes fulfilment", status == 200)
status, _ = call("POST", f"/api/v1/partner/orders/{order_id}/transition", partner,
                 {"to_status": "ACTIVATION_PENDING"})
check("partner hands off to activation pending", status == 200)

# ---- Simulated activation by operations ----
status, r = call("POST", f"/api/v1/operations/orders/{order_id}/transition", ops,
                 {"to_status": "ACTIVATED", "reason": "Simulated prototype activation",
                  "detail": "No real telecom provisioning performed"})
check("operations activates (simulated)", status == 200 and r.get("status") == "ACTIVATED")
status, _ = call("POST", f"/api/v1/operations/orders/{order_id}/transition", ops,
                 {"to_status": "CANCELLED"})
check("terminal ACTIVATED rejects further transition 409", status == 409, str(status))

# ---- Final customer tracking ----
status, detail = call("GET", f"/api/v1/orders/{order_id}", cust)
events = detail.get("events", [])
statuses = [e["to_status"] for e in events]
check("customer sees ACTIVATED status", status == 200 and detail.get("status") == "ACTIVATED")
check("event timeline chronological & complete",
      statuses[-1] == "ACTIVATED" and statuses[0] == "ORDER_PLACED"
      and "ASSIGNED" in statuses and "ON_HOLD" in statuses
      and "ACTIVATION_PENDING" in statuses,
      str(statuses))
actors = {(e["actor_username"], e["actor_role"]) for e in events}
check("events record correct actors", ("qa_ops", "OPERATIONS") in actors
      and ("qa_cust", "CUSTOMER") in actors and ("qa_partner", "PARTNER") in actors)

print("\n==== SUMMARY ====")
fails = [r for r in RESULTS if r[1] == "FAIL"]
for name, state, extra in RESULTS:
    print(f"{state}  {name}  {extra}")
print(f"\n{len(RESULTS) - len(fails)}/{len(RESULTS)} checks passed")
