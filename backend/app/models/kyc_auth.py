"""Request and response models for prototype KYC sessions."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

KycRole = Literal["CUSTOMER", "REVIEWER"]


class KycLoginRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=1024)


class KycSessionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    username: str
    role: KycRole
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: int
    expires_in: int


class KycSessionIdentity(BaseModel):
    model_config = ConfigDict(frozen=True)

    username: str
    role: KycRole
    expires_at: int
