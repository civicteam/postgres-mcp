"""JSON serialization utilities for PostgreSQL data types."""

import datetime
import decimal
from typing import Any

import orjson


def _default(obj: Any) -> Any:
    """Handle types that orjson doesn't natively serialize.

    orjson natively handles: datetime.datetime, datetime.date, datetime.time,
    uuid.UUID, str, int, float, bool, None, dict, list.

    This handler covers remaining PostgreSQL types:
    - decimal.Decimal (numeric columns)
    - datetime.timedelta (interval columns)
    - bytes/memoryview (bytea columns)
    - set/frozenset
    """
    if isinstance(obj, decimal.Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    if isinstance(obj, datetime.timedelta):
        return str(obj)
    if isinstance(obj, memoryview):
        return obj.tobytes().hex()
    if isinstance(obj, bytes):
        return obj.hex()
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def to_jsonable(obj: Any) -> Any:
    """Convert obj to a JSON-serializable Python structure.

    Round-trips through orjson to convert PostgreSQL types
    (Decimal, timedelta, bytes, etc.) to JSON-native types.

    Args:
        obj: The Python object to convert.

    Returns:
        A structure containing only JSON-native Python types.
    """
    return orjson.loads(orjson.dumps(obj, default=_default))


def to_json(obj: Any) -> str:
    """Serialize a Python object to a JSON string.

    Uses orjson for fast serialization with native support for datetime, UUID,
    and other common types. A custom default handler covers PostgreSQL-specific
    types like Decimal, timedelta, and bytes.

    Args:
        obj: The Python object to serialize.

    Returns:
        A pretty-printed JSON string.
    """
    return orjson.dumps(obj, default=_default, option=orjson.OPT_INDENT_2).decode()
