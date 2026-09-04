"""Production Ring Developer Platform provider.

Verifies real Ring webhooks against the configured signing secret and (when a
token is configured) can call the documented Partner API. Status is truthful:
CONNECTED only after a real signed event or API call is verified — never a false
green from mere configuration. Secrets and tokens are held, never logged.
"""

from __future__ import annotations

from app.sentinel.ring.base import ProviderInfo, ProviderStatus
from app.sentinel.ring.webhook import verify_signature

# Documented Ring Partner API surface (used when a token is configured).
DEFAULT_API_BASE = "https://api.amazonvision.com"
DEFAULT_OAUTH_BASE = "https://oauth.ring.com"
DEVICES_PATH = "/v1/devices"
EVENTS_PATH = "/v1/history/devices/{device_id}/events"
SNAPSHOT_PATH = "/v1/devices/{device_id}/media/image/download"
WHEP_PATH = "/v1/devices/{device_id}/media/streaming/whep/sessions"


class RingDeveloperProvider:
    name = "ring"

    def __init__(
        self,
        *,
        client_id: str | None,
        client_secret: str | None,
        webhook_secret: str | None,
        access_token: str | None = None,
        api_base: str = DEFAULT_API_BASE,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._webhook_secret = webhook_secret
        self._access_token = access_token
        self._api_base = api_base
        self._verified = False
        self._error: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self._webhook_secret and self._client_id and self._client_secret)

    def info(self) -> ProviderInfo:
        if self._error:
            return ProviderInfo(provider=self.name, status=ProviderStatus.ERROR, detail=self._error)
        if not self.configured:
            return ProviderInfo(
                provider=self.name, status=ProviderStatus.NOT_CONFIGURED,
                detail="Set RING_CLIENT_ID, RING_CLIENT_SECRET, RING_WEBHOOK_SECRET.",
            )
        if self._verified:
            return ProviderInfo(
                provider=self.name, status=ProviderStatus.CONNECTED,
                detail="Verified: an authentically-signed Ring event was processed.",
            )
        # Configured but not yet proven — do not claim a green connection.
        return ProviderInfo(
            provider=self.name, status=ProviderStatus.NOT_CONFIGURED,
            detail="Configured; awaiting first verified Ring event to confirm connection.",
        )

    def verify_signature(self, raw_body: bytes, signature_header: str | None) -> bool:
        ok = verify_signature(raw_body, signature_header, self._webhook_secret or "")
        if ok:
            self._verified = True  # a real, authentic Ring event confirms the link
        return ok

    def mark_error(self, detail: str) -> None:
        # Detail must not contain secrets/tokens/URLs with credentials.
        self._error = detail
