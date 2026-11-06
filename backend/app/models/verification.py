"""Business registry verification response models."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict


class RegistryVerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    MISMATCH = "MISMATCH"
    UNAVAILABLE = "UNAVAILABLE"
    INCONCLUSIVE = "INCONCLUSIVE"


class RegistryVerificationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    registry_type: Literal["GSTIN", "UDYAM"]
    status: RegistryVerificationStatus
    reason: str
    checked_at: str
    registry_source: str
    compared_fields: list[str]
    mismatched_fields: list[str]
