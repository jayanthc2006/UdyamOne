"""Order lifecycle and snapshot models for Phase 5."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.pricing import QuoteLineItem

OrderStatus = Literal[
    "ORDER_PLACED",
    "ASSIGNED",
    "FULFILMENT_IN_PROGRESS",
    "FULFILMENT_COMPLETED",
    "ACTIVATION_PENDING",
    "ACTIVATED",
    "ON_HOLD",
    "CANCELLED",
]

# Permitted transitions: {from_status: {to_status, ...}}
PERMITTED_TRANSITIONS: dict[str, set[str]] = {
    "ORDER_PLACED": {"ASSIGNED", "ON_HOLD", "CANCELLED"},
    "ASSIGNED": {"FULFILMENT_IN_PROGRESS", "ON_HOLD", "CANCELLED"},
    "FULFILMENT_IN_PROGRESS": {"FULFILMENT_COMPLETED", "ON_HOLD", "CANCELLED"},
    "FULFILMENT_COMPLETED": {"ACTIVATION_PENDING", "ON_HOLD", "CANCELLED"},
    "ACTIVATION_PENDING": {"ACTIVATED", "ON_HOLD", "CANCELLED"},
    "ACTIVATED": set(),
    "ON_HOLD": {"ORDER_PLACED", "ASSIGNED", "FULFILMENT_IN_PROGRESS", "CANCELLED"},
    "CANCELLED": set(),
}

# Which roles may trigger which transitions
TRANSITION_ROLES: dict[tuple[str, str], set[str]] = {
    ("ORDER_PLACED", "ASSIGNED"): {"OPERATIONS"},
    ("ORDER_PLACED", "ON_HOLD"): {"OPERATIONS"},
    ("ORDER_PLACED", "CANCELLED"): {"OPERATIONS", "CUSTOMER"},
    ("ASSIGNED", "FULFILMENT_IN_PROGRESS"): {"PARTNER"},
    ("ASSIGNED", "ON_HOLD"): {"OPERATIONS"},
    ("ASSIGNED", "CANCELLED"): {"OPERATIONS"},
    ("FULFILMENT_IN_PROGRESS", "FULFILMENT_COMPLETED"): {"PARTNER"},
    ("FULFILMENT_IN_PROGRESS", "ON_HOLD"): {"OPERATIONS", "PARTNER"},
    ("FULFILMENT_IN_PROGRESS", "CANCELLED"): {"OPERATIONS"},
    ("FULFILMENT_COMPLETED", "ACTIVATION_PENDING"): {"PARTNER", "OPERATIONS"},
    ("FULFILMENT_COMPLETED", "ON_HOLD"): {"OPERATIONS"},
    ("FULFILMENT_COMPLETED", "CANCELLED"): {"OPERATIONS"},
    ("ACTIVATION_PENDING", "ACTIVATED"): {"OPERATIONS"},
    ("ACTIVATION_PENDING", "ON_HOLD"): {"OPERATIONS"},
    ("ACTIVATION_PENDING", "CANCELLED"): {"OPERATIONS"},
    ("ON_HOLD", "ORDER_PLACED"): {"OPERATIONS"},
    ("ON_HOLD", "ASSIGNED"): {"OPERATIONS"},
    ("ON_HOLD", "FULFILMENT_IN_PROGRESS"): {"OPERATIONS"},
    ("ON_HOLD", "CANCELLED"): {"OPERATIONS"},
}


class OrderSnapshot(BaseModel):
    """Immutable pricing and product snapshot captured at order creation."""

    model_config = ConfigDict(frozen=True)

    snapshot_version: int = 1
    quote_id: str
    line_items: list[QuoteLineItem]
    total_monthly_min_inr: int = Field(ge=0)
    total_monthly_max_inr: int = Field(ge=0)
    total_one_time_setup_inr: int = Field(ge=0)
    quote_created_at: str
    disclosure: str = (
        "This is a prototype order request. Pricing is an estimate only and does not "
        "constitute a binding commercial offer, contract, or commitment to supply services."
    )


class OrderEvent(BaseModel):
    """One entry in the append-only order history."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    order_id: str
    event_type: str
    from_status: str | None
    to_status: str
    actor_username: str
    actor_role: str
    reason: str | None
    detail: str | None
    created_at: str


class OrderAssignment(BaseModel):
    """Current or historical partner assignment for an order."""

    model_config = ConfigDict(frozen=True)

    assignment_id: str
    order_id: str
    partner_username: str
    assigned_by_username: str
    assigned_at: str
    reason: str | None
    superseded_at: str | None


class OrderRecord(BaseModel):
    """Full order record including snapshot and current state."""

    model_config = ConfigDict(frozen=True)

    order_id: str
    applicant_id: str
    status: OrderStatus
    snapshot: OrderSnapshot
    created_at: str
    updated_at: str
    current_assignment: OrderAssignment | None = None
    events: list[OrderEvent] = Field(default_factory=list)


# ── Request / Response schemas ──────────────────────────────────────────────

class PlaceOrderRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    applicant_id: str = Field(min_length=1)
    confirmed: bool


class TransitionOrderRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    to_status: OrderStatus
    reason: str | None = Field(default=None, max_length=500)
    detail: str | None = Field(default=None, max_length=1000)


class AssignPartnerRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    partner_username: str = Field(min_length=1, max_length=100)
    reason: str | None = Field(default=None, max_length=500)


class OrderSummary(BaseModel):
    """Lightweight order record for list views."""

    model_config = ConfigDict(frozen=True)

    order_id: str
    applicant_id: str
    status: OrderStatus
    created_at: str
    updated_at: str
    partner_username: str | None = None
    total_monthly_min_inr: int
    total_monthly_max_inr: int
    total_one_time_setup_inr: int
