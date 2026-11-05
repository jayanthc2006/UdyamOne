"""Login and current-session endpoints for the KYC prototype."""

from time import time

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.kyc_auth import (
    KycLoginRequest,
    KycSessionIdentity,
    KycSessionResponse,
)
from app.security.kyc_auth import (
    authenticate_account,
    create_session_token,
    current_auth_configuration,
    get_current_kyc_principal,
    KycPrincipal,
)

router = APIRouter(prefix="/auth", tags=["prototype-auth"])


@router.post("/session", response_model=KycSessionResponse)
def create_kyc_session(request: KycLoginRequest) -> KycSessionResponse:
    """Issue a short-lived signed session for a backend-configured account."""
    configuration = current_auth_configuration()
    account = authenticate_account(
        request.username,
        request.password,
        configuration,
    )
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username or password is incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token, expires_at = create_session_token(account, configuration.secret)
    return KycSessionResponse(
        username=account.username,
        role=account.role,
        access_token=access_token,
        expires_at=expires_at,
        expires_in=max(0, expires_at - int(time())),
    )


@router.get("/session", response_model=KycSessionIdentity)
def get_kyc_session(
    principal: KycPrincipal = Depends(get_current_kyc_principal),
) -> KycSessionIdentity:
    """Validate the bearer token and return its server-verified identity."""
    return KycSessionIdentity(
        username=principal.username,
        role=principal.role,
        expires_at=principal.expires_at,
    )
