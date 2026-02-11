from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
import pytest_asyncio

from postgres_mcp.artifacts import ExplainPlanArtifact
from postgres_mcp.server import explain_query


@pytest_asyncio.fixture
async def mock_safe_sql_driver():
    """Create a mock SafeSqlDriver for testing."""
    driver = MagicMock()
    return driver


@pytest.fixture
def mock_explain_plan_tool():
    """Create a mock ExplainPlanTool."""
    tool = MagicMock()
    tool.explain = AsyncMock()
    tool.explain_analyze = AsyncMock()
    tool.explain_with_hypothetical_indexes = AsyncMock()
    return tool


class MockCell:
    def __init__(self, data):
        self.cells = data


@pytest.mark.asyncio
async def test_explain_query_integration():
    """Test the entire explain_query tool end-to-end."""
    mock_artifact = MagicMock(spec=ExplainPlanArtifact)
    mock_artifact.to_text.return_value = "Seq Scan on users"

    mock_tool = MagicMock()
    mock_tool.explain = AsyncMock(return_value=mock_artifact)

    with patch("postgres_mcp.server.get_sql_driver"):
        with patch("postgres_mcp.server.ExplainPlanTool", return_value=mock_tool):
            result = await explain_query("SELECT * FROM users", analyze=False, hypothetical_indexes=[])

            assert isinstance(result, str)
            assert result == "Seq Scan on users"


@pytest.mark.asyncio
async def test_explain_query_with_analyze_integration():
    """Test the explain_query tool with analyze=True."""
    mock_artifact = MagicMock(spec=ExplainPlanArtifact)
    mock_artifact.to_text.return_value = "Seq Scan on users (actual rows=100)"

    mock_tool = MagicMock()
    mock_tool.explain_analyze = AsyncMock(return_value=mock_artifact)

    with patch("postgres_mcp.server.get_sql_driver"):
        with patch("postgres_mcp.server.ExplainPlanTool", return_value=mock_tool):
            result = await explain_query("SELECT * FROM users", analyze=True, hypothetical_indexes=[])

            assert isinstance(result, str)
            assert result == "Seq Scan on users (actual rows=100)"


@pytest.mark.asyncio
async def test_explain_query_with_hypothetical_indexes_integration():
    """Test the explain_query tool with hypothetical indexes."""
    mock_artifact = MagicMock(spec=ExplainPlanArtifact)
    mock_artifact.to_text.return_value = "Index Scan using hypo_idx"

    mock_tool = MagicMock()
    mock_tool.explain_with_hypothetical_indexes = AsyncMock(return_value=mock_artifact)

    test_sql = "SELECT * FROM users WHERE email = 'test@example.com'"
    test_indexes = [{"table": "users", "columns": ["email"]}]

    # Mock check_hypopg_installation_status to return installed
    with patch("postgres_mcp.server.check_hypopg_installation_status", return_value=(True, "")):
        mock_safe_driver = MagicMock()
        with patch("postgres_mcp.server.get_sql_driver", return_value=mock_safe_driver):
            with patch("postgres_mcp.server.ExplainPlanTool", return_value=mock_tool):
                result = await explain_query(test_sql, analyze=False, hypothetical_indexes=test_indexes)

                assert isinstance(result, str)
                assert result == "Index Scan using hypo_idx"


@pytest.mark.asyncio
async def test_explain_query_missing_hypopg_integration():
    """Test the explain_query tool when hypopg extension is missing."""
    test_sql = "SELECT * FROM users WHERE email = 'test@example.com'"
    test_indexes = [{"table": "users", "columns": ["email"]}]

    missing_ext_message = "The hypopg extension is required"

    # Mock check_hypopg_installation_status to return not installed
    with patch("postgres_mcp.server.check_hypopg_installation_status", return_value=(False, missing_ext_message)):
        mock_safe_driver = MagicMock()
        with patch("postgres_mcp.server.get_sql_driver", return_value=mock_safe_driver):
            with patch("postgres_mcp.server.ExplainPlanTool"):
                result = await explain_query(test_sql, analyze=False, hypothetical_indexes=test_indexes)

                assert isinstance(result, str)
                assert result == missing_ext_message


@pytest.mark.asyncio
async def test_explain_query_error_handling_integration():
    """Test the explain_query tool's error handling."""
    error_message = "Error executing query"

    # Patch the get_sql_driver to throw an exception
    with patch(
        "postgres_mcp.server.get_sql_driver",
        side_effect=Exception(error_message),
    ):
        with pytest.raises(Exception, match=error_message):
            await explain_query("INVALID SQL")
