"""Conversational AI business advisor API route."""

from fastapi import APIRouter, HTTPException, status

from app.models.advisor import AdvisorChatRequest, AdvisorChatResponse
from app.services.advisor_service import (
    AdvisorNotConfiguredError,
    AdvisorProviderTimeoutError,
    AdvisorProviderUnavailableError,
    chat_with_advisor,
)

router = APIRouter(prefix="/advisor", tags=["advisor"])


@router.post("/chat", response_model=AdvisorChatResponse)
def advisor_chat(request: AdvisorChatRequest) -> AdvisorChatResponse:
    """Return one non-persistent advisor turn with deterministic recommendations."""
    try:
        return chat_with_advisor(request)
    except AdvisorNotConfiguredError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except AdvisorProviderTimeoutError as error:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(error),
        ) from error
    except AdvisorProviderUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error
