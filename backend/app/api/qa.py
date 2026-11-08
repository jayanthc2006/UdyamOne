"""QA-only routes, enabled only in isolated QA mode."""

import json
import os
from fastapi import APIRouter, HTTPException

from app.models.applicant import ApplicantProfile
from app.models.business_profile import BusinessProfile
from app.models.pricing import ProductSelection, QuoteRequest
from app.models.recommendation import RecommendationResponse
from app.services.applicant_service import create_applicant, save_quote_preview
from app.services.pricing_service import generate_quote

router = APIRouter(prefix="/qa", tags=["qa"])

_QA_CUSTOMER_USERNAME = "qa_cust"


def _grant_customer_ownership(applicant_id: str) -> None:
    """Grant the QA customer ownership of the freshly seeded applicant.

    QA-mode only: the account configuration is re-read from the environment on
    every authenticated request, so appending the applicant ID to the QA
    customer's record takes effect for subsequent requests without restarting.
    """
    raw = os.getenv("UDYAMONE_KYC_AUTH_USERS", "")
    if not raw.strip():
        return
    try:
        accounts = json.loads(raw)
    except json.JSONDecodeError:
        return
    if not isinstance(accounts, list):
        return
    for entry in accounts:
        if (
            isinstance(entry, dict)
            and entry.get("username") == _QA_CUSTOMER_USERNAME
            and isinstance(entry.get("applicant_ids"), list)
            and applicant_id not in entry["applicant_ids"]
        ):
            entry["applicant_ids"].append(applicant_id)
    os.environ["UDYAMONE_KYC_AUTH_USERS"] = json.dumps(accounts)


@router.post("/seed")
def seed_applicant(payload: dict) -> dict:
    if os.getenv("UDYAMONE_QA_MODE") != "1":
        raise HTTPException(status_code=404, detail="Not found")
    profile_data = {
        "business_name": payload.get("business_name", "QA Co"),
        "business_type": "Micro retail",
        "city": "Hyderabad",
        "business_profile": BusinessProfile(city_tier=1, employee_count=5, site_count=1, gstin_verified=False),
        "business_segment": "micro",
        "gstin_self_reported_status": "Not verified",
        "primary_requirements": ["connectivity"],
    }
    profile = ApplicantProfile(**profile_data)
    record = create_applicant(profile, RecommendationResponse(bundles=[], unsupported_requirements=[]))
    quote = generate_quote(QuoteRequest(business_profile=profile.business_profile, selected_products=[ProductSelection(product_id="P01", quantity=1)]))
    save_quote_preview(record.applicant_id, quote)
    _grant_customer_ownership(record.applicant_id)
    return {"applicant_id": record.applicant_id}
