"""Customer-facing order routes."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.order import (
    OrderRecord,
    OrderSummary,
    PlaceOrderRequest,
    TransitionOrderRequest,
)
from app.security.kyc_auth import KycPrincipal, get_current_kyc_principal, require_kyc_role
from app.services.applicant_service import ApplicantNotFoundError
from app.services.order_service import (
    DuplicateOrderError,
    InvalidQuoteError,
    OrderAuthorizationError,
    OrderNotFoundError,
    OrderStateError,
    get_order,
    list_orders_for_applicant,
    place_order,
    transition_order,
)

router = APIRouter(prefix="/orders", tags=["orders"])


def _require_customer_owns_order(principal: KycPrincipal, order: OrderRecord) -> None:
    if order.applicant_id not in principal.applicant_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="You are not authorized to access this order.")


@router.post("", response_model=OrderRecord, status_code=status.HTTP_201_CREATED)
def create_order(
    request: PlaceOrderRequest,
    principal: KycPrincipal = Depends(get_current_kyc_principal),
) -> OrderRecord:
    """Convert the applicant's latest quote into a confirmed prototype order."""
    require_kyc_role(principal, "CUSTOMER")
    if request.applicant_id not in principal.applicant_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="You are not authorized to place an order for this applicant.")
    if not request.confirmed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Explicit confirmation is required to place an order.")
    try:
        return place_order(request.applicant_id, principal.username, principal.role)
    except ApplicantNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except (InvalidQuoteError, DuplicateOrderError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except OrderAuthorizationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e


@router.get("/applicant/{applicant_id}", response_model=list[OrderSummary])
def get_applicant_orders(
    applicant_id: str,
    principal: KycPrincipal = Depends(get_current_kyc_principal),
) -> list[OrderSummary]:
    """List all orders for an applicant the customer owns."""
    require_kyc_role(principal, "CUSTOMER")
    if applicant_id not in principal.applicant_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="You are not authorized to view orders for this applicant.")
    return list_orders_for_applicant(applicant_id)


@router.get("/{order_id}", response_model=OrderRecord)
def get_order_detail(
    order_id: str,
    principal: KycPrincipal = Depends(get_current_kyc_principal),
) -> OrderRecord:
    """Get full order detail; customers may only see their own orders."""
    require_kyc_role(principal, "CUSTOMER")
    try:
        order = get_order(order_id)
    except OrderNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    if order.applicant_id not in principal.applicant_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="You are not authorized to access this order.")
    return order


@router.post("/{order_id}/cancel", response_model=OrderRecord)
def cancel_order(
    order_id: str,
    principal: KycPrincipal = Depends(get_current_kyc_principal),
) -> OrderRecord:
    """Customer cancels their own ORDER_PLACED order."""
    require_kyc_role(principal, "CUSTOMER")
    try:
        order = get_order(order_id)
    except OrderNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    _require_customer_owns_order(principal, order)
    try:
        return transition_order(
            order_id,
            TransitionOrderRequest(to_status="CANCELLED", reason="Cancelled by customer."),
            principal.username,
            principal.role,
        )
    except (OrderStateError, OrderAuthorizationError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
