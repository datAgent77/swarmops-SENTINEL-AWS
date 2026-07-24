"""Domain error types, mapped to a consistent API error envelope by the API layer."""

from __future__ import annotations


class DomainError(Exception):
    code: str = "DOMAIN_ERROR"
    http_status: int = 400

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(DomainError):
    code = "NOT_FOUND"
    http_status = 404


class ConflictError(DomainError):
    code = "CONFLICT"
    http_status = 409


class InvalidStateError(DomainError):
    code = "INVALID_STATE"
    http_status = 409


class InvalidTransitionError(InvalidStateError):
    code = "INVALID_STATE_TRANSITION"
