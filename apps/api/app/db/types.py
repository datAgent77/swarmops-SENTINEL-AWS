"""Custom column types."""

from __future__ import annotations

from enum import Enum
from typing import Any

from sqlalchemy import String
from sqlalchemy.types import TypeDecorator


class EnumString(TypeDecorator):
    """Stores an Enum as its string value; loads it back as the Enum.

    Underlying storage is VARCHAR, so it round-trips cleanly and keeps the schema
    simple (no native Postgres enum types to migrate).
    """

    impl = String
    cache_ok = True

    def __init__(self, enum_cls: type[Enum], length: int = 30, **kwargs: Any) -> None:
        self.enum_cls = enum_cls
        super().__init__(length=length, **kwargs)

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, self.enum_cls):
            return value.value
        return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        return self.enum_cls(value)
