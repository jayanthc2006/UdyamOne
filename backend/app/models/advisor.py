"""Typed request and response models for the conversational business advisor."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.business_profile import BusinessProfile
from app.models.recommendation import (
    BusinessSegment,
    PrimaryRequirement,
    RecommendationResponse,
)

AdvisorLanguage = Literal["en", "hi", "te", "ta", "kn"]
AdvisorMessageRole = Literal["user", "assistant"]


class AdvisorMessage(BaseModel):
    """One bounded, in-memory conversation message."""

    model_config = ConfigDict(frozen=True)

    role: AdvisorMessageRole
    content: str = Field(min_length=1, max_length=1200)


class AdvisorChatRequest(BaseModel):
    """Minimum customer context needed to interpret an advisor turn."""

    business_profile: BusinessProfile
    business_segment: BusinessSegment
    primary_requirements: list[PrimaryRequirement] = Field(default_factory=list, max_length=4)
    messages: list[AdvisorMessage] = Field(min_length=1, max_length=12)
    language: AdvisorLanguage = "en"

    @field_validator("primary_requirements")
    @classmethod
    def requirements_must_be_unique(
        cls, requirements: list[PrimaryRequirement]
    ) -> list[PrimaryRequirement]:
        if len(requirements) != len(set(requirements)):
            raise ValueError("primary_requirements must not contain duplicates.")
        return requirements

    @field_validator("messages")
    @classmethod
    def latest_message_must_be_from_customer(
        cls, messages: list[AdvisorMessage]
    ) -> list[AdvisorMessage]:
        if messages[-1].role != "user":
            raise ValueError("The latest conversation message must be from the user.")
        return messages


class AdvisorChatResponse(BaseModel):
    """Grounded advisor reply and optional deterministic recommendation data."""

    reply: str
    language: AdvisorLanguage
    extracted_requirements: list[PrimaryRequirement]
    needs_clarification: bool
    recommendations_refreshed: bool
    recommendations: RecommendationResponse | None = None
    privacy_notice: str = (
        "Your message is processed by the configured AI provider for this reply and is "
        "not saved by UdyamOne."
    )
    prototype_notice: str = (
        "Recommendations and prices are prototype outputs based on the current catalogue "
        "and are subject to commercial verification."
    )
