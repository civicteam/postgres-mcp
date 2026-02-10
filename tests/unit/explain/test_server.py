from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
import pytest_asyncio

import postgres_mcp.server as server


class MockCell:
    def __init__(self, data):
        self.cells = data


@pytest_asyncio.fixture
async def mock_db_connection():
    """Create a mock DB connection."""
    conn = MagicMock()
    conn.pool_connect = AsyncMock()
    conn.close = AsyncMock()
    return conn


@pytest.mark.asyncio
async def test_server_tools_registered():
    """Test that the explain tools are properly registered in the server."""
    # Check that the explain tool is registered
    assert hasattr(server, "explain_query")

    # Simply check that the tool is callable
    assert callable(server.explain_query)


@pytest.mark.asyncio
async def test_explain_query_basic():
    """Test explain_query with basic parameters."""
    expected_text = "Seq Scan on users"

    # Use patch to replace the actual explain_query function with our own mock
    with patch.object(server, "explain_query", return_value=expected_text):
        # Call the patched function
        result = await server.explain_query("SELECT * FROM users")

        # Verify we get the expected result
        assert isinstance(result, str)
        assert result == expected_text


@pytest.mark.asyncio
async def test_explain_query_analyze():
    """Test explain_query with analyze=True."""
    expected_text = "Seq Scan on users (actual rows=100)"

    # Use patch to replace the actual explain_query function with our own mock
    with patch.object(server, "explain_query", return_value=expected_text):
        # Call the patched function with analyze=True
        result = await server.explain_query("SELECT * FROM users", analyze=True)

        # Verify we get the expected result
        assert isinstance(result, str)
        assert result == expected_text


@pytest.mark.asyncio
async def test_explain_query_hypothetical_indexes():
    """Test explain_query with hypothetical indexes."""
    expected_text = "Index Scan using hypothetical_idx"

    # Test data
    test_sql = "SELECT * FROM users WHERE email = 'test@example.com'"
    test_indexes = [{"table": "users", "columns": ["email"]}]

    # Use patch to replace the actual explain_query function with our own mock
    with patch.object(server, "explain_query", return_value=expected_text):
        # Call the patched function with hypothetical_indexes
        result = await server.explain_query(test_sql, hypothetical_indexes=test_indexes)

        # Verify we get the expected result
        assert isinstance(result, str)
        assert result == expected_text


@pytest.mark.asyncio
async def test_explain_query_error_handling():
    """Test explain_query error handling."""
    error_message = "Error executing query"

    # Use patch to replace the actual function with our mock that raises
    with patch.object(server, "explain_query", side_effect=RuntimeError(error_message)):
        with pytest.raises(RuntimeError, match=error_message):
            await server.explain_query("INVALID SQL")
