"""Tests for JSON serialization utilities."""

import datetime
import json
import uuid
from decimal import Decimal

import mcp.types as types
import pytest

from postgres_mcp.json_utils import to_json
from postgres_mcp.server import format_text_response


class TestToJson:
    """Tests for the to_json serialization function."""

    def test_basic_types(self):
        """Test serialization of basic Python types."""
        result = json.loads(to_json({"str": "hello", "int": 42, "float": 3.14, "bool": True, "null": None}))
        assert result == {"str": "hello", "int": 42, "float": 3.14, "bool": True, "null": None}

    def test_datetime(self):
        """Test serialization of datetime objects (handled natively by orjson)."""
        dt = datetime.datetime(2024, 1, 15, 10, 30, 0, tzinfo=datetime.timezone.utc)
        result = json.loads(to_json({"created_at": dt}))
        assert result["created_at"] == "2024-01-15T10:30:00+00:00"

    def test_date(self):
        """Test serialization of date objects."""
        d = datetime.date(2024, 6, 15)
        result = json.loads(to_json({"date": d}))
        assert result["date"] == "2024-06-15"

    def test_time(self):
        """Test serialization of time objects."""
        t = datetime.time(14, 30, 0)
        result = json.loads(to_json({"time": t}))
        assert result["time"] == "14:30:00"

    def test_uuid(self):
        """Test serialization of UUID objects (handled natively by orjson)."""
        u = uuid.UUID("12345678-1234-5678-1234-567812345678")
        result = json.loads(to_json({"id": u}))
        assert result["id"] == "12345678-1234-5678-1234-567812345678"

    def test_decimal_whole_number(self):
        """Test serialization of Decimal with whole number value."""
        result = json.loads(to_json({"count": Decimal("42")}))
        assert result["count"] == 42
        assert isinstance(result["count"], int)

    def test_decimal_fractional(self):
        """Test serialization of Decimal with fractional value."""
        result = json.loads(to_json({"price": Decimal("19.99")}))
        assert result["price"] == pytest.approx(19.99)

    def test_timedelta(self):
        """Test serialization of timedelta (PostgreSQL interval type)."""
        td = datetime.timedelta(days=1, hours=2, minutes=30)
        result = json.loads(to_json({"interval": td}))
        assert result["interval"] == "1 day, 2:30:00"

    def test_bytes(self):
        """Test serialization of bytes (PostgreSQL bytea type)."""
        result = json.loads(to_json({"data": b"\xde\xad\xbe\xef"}))
        assert result["data"] == "deadbeef"

    def test_memoryview(self):
        """Test serialization of memoryview."""
        mv = memoryview(b"\xca\xfe")
        result = json.loads(to_json({"data": mv}))
        assert result["data"] == "cafe"

    def test_set(self):
        """Test serialization of sets."""
        result = json.loads(to_json({"tags": {1, 2, 3}}))
        assert sorted(result["tags"]) == [1, 2, 3]

    def test_frozenset(self):
        """Test serialization of frozensets."""
        result = json.loads(to_json({"tags": frozenset([1, 2])}))
        assert sorted(result["tags"]) == [1, 2]

    def test_list_of_dicts(self):
        """Test serialization of list of dicts (typical SQL result rows)."""
        rows = [
            {"name": "users", "count": Decimal("1000"), "created": datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)},
            {"name": "orders", "count": Decimal("5000"), "created": datetime.datetime(2024, 6, 1, tzinfo=datetime.timezone.utc)},
        ]
        result = json.loads(to_json(rows))
        assert len(result) == 2
        assert result[0]["name"] == "users"
        assert result[0]["count"] == 1000
        assert result[1]["name"] == "orders"
        assert result[1]["count"] == 5000

    def test_unsupported_type_raises(self):
        """Test that unsupported types raise TypeError."""
        with pytest.raises(TypeError, match="not JSON serializable"):
            to_json({"obj": object()})

    def test_nested_structures(self):
        """Test serialization of nested structures with mixed types."""
        data = {
            "query": "SELECT * FROM users",
            "stats": {
                "total_time": Decimal("1234.56"),
                "calls": 100,
                "last_run": datetime.datetime(2024, 3, 15, 12, 0, 0, tzinfo=datetime.timezone.utc),
            },
        }
        result = json.loads(to_json(data))
        assert result["stats"]["total_time"] == pytest.approx(1234.56)
        assert result["stats"]["calls"] == 100

    def test_none_value(self):
        """Test serialization of None produces JSON null."""
        result = to_json(None)
        assert result.strip() == "null"

    def test_empty_list(self):
        """Test serialization of empty list."""
        result = json.loads(to_json([]))
        assert result == []


class TestFormatTextResponse:
    """Tests for the format_text_response function."""

    def test_string_passthrough(self):
        """Test that string input is passed through as-is."""
        result = format_text_response("hello world")
        assert len(result) == 1
        assert isinstance(result[0], types.TextContent)
        assert result[0].text == "hello world"

    def test_structured_data_produces_json(self):
        """Test that structured data is serialized to valid JSON."""
        data = [{"schema_name": "public", "schema_owner": "postgres"}]
        result = format_text_response(data)
        assert len(result) == 1
        assert isinstance(result[0], types.TextContent)
        parsed = json.loads(result[0].text)
        assert parsed[0]["schema_name"] == "public"

    def test_dict_produces_json(self):
        """Test that a dict is serialized to valid JSON."""
        data = {"name": "users", "type": "table"}
        result = format_text_response(data)
        assert isinstance(result[0], types.TextContent)
        parsed = json.loads(result[0].text)
        assert parsed["name"] == "users"

    def test_empty_string(self):
        """Test that empty string is passed through as-is."""
        result = format_text_response("")
        assert isinstance(result[0], types.TextContent)
        assert result[0].text == ""

    def test_simulated_sql_rows_with_mixed_types(self):
        """Test format_text_response with data resembling real SQL query results."""
        rows = [
            {
                "query": "SELECT * FROM users WHERE id = $1",
                "calls": 1500,
                "total_exec_time": Decimal("4523.789"),
                "mean_exec_time": Decimal("3.016"),
                "rows": 1500,
                "last_call": datetime.datetime(2024, 8, 1, 14, 30, tzinfo=datetime.timezone.utc),
            },
            {
                "query": "INSERT INTO logs (msg) VALUES ($1)",
                "calls": 50000,
                "total_exec_time": Decimal("12000"),
                "mean_exec_time": Decimal("0.24"),
                "rows": 50000,
                "last_call": datetime.datetime(2024, 8, 1, 15, 0, tzinfo=datetime.timezone.utc),
            },
        ]
        result = format_text_response(rows)
        assert isinstance(result[0], types.TextContent)
        parsed = json.loads(result[0].text)
        assert len(parsed) == 2
        assert parsed[0]["calls"] == 1500
        assert parsed[0]["total_exec_time"] == pytest.approx(4523.789)
        assert parsed[1]["total_exec_time"] == 12000
        assert isinstance(parsed[1]["total_exec_time"], int)
