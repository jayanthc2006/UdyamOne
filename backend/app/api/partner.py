"""Partner-facing fulfilment routes."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.order import OrderRecord, OrderSummary, TransitionOrderRequest
from app.security.kyc_auth import KycPrincipal, get_current_kyc_principal, require_kyc_role
from app.services.order_service import (
    OrderAuthorizationError,
    OrderNotFoundError,
    OrderStateError,
    get_order,
    list_orders_for_partner,
    transition_order,
)

router = APIRouter(prefix="/partner/orders", tags=["partner"])


@router.get("", response_model=list[OrderSummary])
def list_assigned_orders(
    principal: KycPrincipal = Depends(get_current_kyc_principal),
) -> list[OrderSummary]:
    require_kyc_role(principal, "PARTNER")
    return list_orders_for_partner(principal.username)


@router.get("/{order_id}", response_model=OrderRecord)
def get_assigned_order(
    order_id: str,
    principal: KycPrincipal = Depends(get_current_kyc_principal),
) -> OrderRecord:
    require_kyc_role(principal, "PARTNER")
    try:
        order = get_order(order_id)
    except OrderNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    if (
        order.current_assignment is None
        or order.current_assignment.partner_username != principal.username
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="You are not the assigned partner for this order.")
    return order


@router.post("/{order_id}/transition", response_model=OrderRecord)
def partner_transition(
    order_id: str,
    request: TransitionOrderRequest,
    principal: KycPrincipal = Depends(get_current_kyc_principal),
) -> OrderRecord:
    require_kyc_role(principal, "PARTNER")
    try:
        return transition_order(order_id, request, principal.username, principal.role)
    except OrderNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except (OrderStateError, OrderAuthorizationError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
