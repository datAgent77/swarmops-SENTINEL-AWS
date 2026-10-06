"""Test configuration for Sentinel.

Sentinel's authoritative state is in-process (no database), so the suite needs no
schema setup. Each test constructs its own OfficerService or a FastAPI TestClient.
"""
