"""Ring provider contract, status, and payload shapes.

The payload models mirror the documented Ring Partner API webhook structure
(``meta`` + ``data`` with ``attributes``). ``extra="ignore"`` so Ring may add
fields without breaking ingestion.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class ProviderStatus(str, Enum):
    CONNECTED = "CONNECTED"          # verified: a real signed event / API call succeeded
    DEMO_MODE = "DEMO_MODE"         # simulator / playground
    NOT_CONFIGURED = "NOT_CONFIGURED"
    ERROR = "ERROR"


class RingError(Exception):
    """Base for Ring integration errors."""


class RingSignatureError(RingError):
    """Raised when webhook signature verification fails."""


class RingConfigError(RingError):
    """Raised when a real Ring call is attempted without configuration."""


class RingEventMeta(BaseModel):
    model_config = ConfigDict(extra="ignore")
    request_id: str
    account_id: str | None = None
    timestamp: int | None = None   # epoch milliseconds, per Ring


class RingEventData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: str                       # e.g. "motion_detected", "button_press"
    id: str                         # Ring device id
    attributes: dict[str, Any] = Field(default_factory=dict)


class RingWebhookEnvelope(BaseModel):
    """The documented top-level Ring webhook payload."""

    model_config = ConfigDict(extra="ignore")
    meta: RingEventMeta
    data: RingEventData


class ProviderInfo(BaseModel):
    provider: str
    status: ProviderStatus
    detail: str = ""


@runtime_checkable
class RingProvider(Protocol):
    """Sensing-provider contract. Implementations: developer, simulator, mock."""

    name: str

    def info(self) -> ProviderInfo: ...

    def verify_signature(self, raw_body: bytes, signature_header: str | None) -> bool:
        """Return True iff the raw body is authentically signed by Ring."""
        ...
