"""Ring provider + ingest-service selection (the only place that picks a provider).

Selection (``RING_PROVIDER``): ``developer`` | ``simulator`` | ``mock`` | ``auto``.
``auto`` uses the real developer provider when Ring credentials are configured,
otherwise the Playground simulator (DEMO_MODE) so the demo never needs real keys.
"""

from __future__ import annotations

from app.config import Settings, get_settings
from app.sentinel.ring.base import RingProvider
from app.sentinel.ring.developer import RingDeveloperProvider
from app.sentinel.ring.ingest import RingIngestService
from app.sentinel.ring.simulator import RingSimulatorProvider

# Signs simulated events only. Not a real credential; never protects real data.
DEMO_WEBHOOK_SECRET = "sentinel-demo-ring-secret"


def effective_webhook_secret(settings: Settings) -> str:
    return settings.ring_webhook_secret or DEMO_WEBHOOK_SECRET


def build_provider(settings: Settings) -> RingProvider:
    mode = (settings.ring_provider or "auto").lower()
    developer = RingDeveloperProvider(
        client_id=settings.ring_client_id,
        client_secret=settings.ring_client_secret,
        webhook_secret=settings.ring_webhook_secret,
        access_token=settings.ring_access_token,
        api_base=settings.ring_api_base,
    )
    if mode == "developer":
        return developer
    if mode == "simulator":
        return RingSimulatorProvider(effective_webhook_secret(settings))
    if mode == "auto":
        return developer if developer.configured else RingSimulatorProvider(effective_webhook_secret(settings))
    # "mock" or unknown → simulator is the safe non-network default.
    return RingSimulatorProvider(effective_webhook_secret(settings))


def get_simulator(settings: Settings) -> RingSimulatorProvider:
    """A simulator that signs with the SAME secret the active provider verifies,
    so simulated events pass the real signature check."""
    return RingSimulatorProvider(effective_webhook_secret(settings))


_service: RingIngestService | None = None


def get_ingest_service() -> RingIngestService:
    """Process-wide ingest service so dedup + correlation state persist across
    webhook calls (durable persistence arrives in P03)."""
    global _service
    if _service is None:
        settings = get_settings()
        _service = RingIngestService(
            build_provider(settings),
            correlator=None,  # default window from settings applied below
        )
    return _service


def reset_ingest_service() -> None:
    """Testing hook to reset in-memory dedup/correlation state."""
    global _service
    _service = None
