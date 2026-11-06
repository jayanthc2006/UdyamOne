"""Operations-facing order management routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.models.order import (
    AssignPartnerRequest,
    OrderRecord,
    OrderSummary,
    TransitionOrderRequest,
)
from app.security.kyc_auth import (
    KycPrincipal,
    get_current_kyc_principal,
    load_kyc_auth_configuration,
    require_kyc_role,
    KycAuthConfigurationError,
)
from app.services.order_service import (
    OrderAuthorizationError,
    OrderNotFoundError,
    OrderStateError,
    assign_partner,
    get_order,
    list_all_orders,
    transition_order,
)

router = APIRouter(prefix="/operations/orders", tags=["operations"])


def _load_accounts() -> dict:
    try:
        return load_kyc_auth_configuration().accounts
    except KycAuthConfigurationError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e


@router.get("", response_model=list[OrderSummary])
def list_orders(
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    principal: KycPrincipal = Depends(get_current_kyc_principal),
) -> list[OrderSummary]:
    require_kyc_role(principal, "OPERATIONS")
    return list_all_orders(status_filter=status_filter, search=search)


@router.get("/{order_id}", response_model=OrderRecord)
def get_order_detail(
    order_id: str,
    principal: KycPrincipal = Depends(get_current_kyc_principal),
) -> OrderRecord:
    require_kyc_role(principal, "OPERATIONS")
    try:
        return get_order(order_id)
    except OrderNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/{order_id}/assign", response_model=OrderRecord)
def assign_order_partner(
    order_id: str,
    request: AssignPartnerRequest,
    principal: KycPrincipal = Depends(get_current_kyc_principal),
) -> OrderRecord:
    require_kyc_role(principal, "OPERATIONS")
    accounts = _load_accounts()
    try:
        return assign_partner(order_id, request, principal.username, principal.role, accounts)
    except OrderNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except (OrderStateError, OrderAuthorizationError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.post("/{order_id}/transition", response_model=OrderRecord)
def transition_order_status(
    order_id: str,
    request: TransitionOrderRequest,
    principal: KycPrincipal = Depends(get_current_kyc_principal),
) -> OrderRecord:
    require_kyc_role(principal, "OPERATIONS")
    try:
        return transition_order(order_id, request, principal.username, principal.role)
    except OrderNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except (OrderStateError, OrderAuthorizationError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
