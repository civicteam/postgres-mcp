from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from mcp.types import CallToolResult

import postgres_mcp.server as server


class MockRow:
    def __init__(self, cells):
        self.cells = cells


@pytest.mark.asyncio
async def test_get_object_details_output_schema_is_structured():
    """Ensure object-details keeps a structured output schema."""
    tools = await server.mcp.list_tools()
    tool = next(t for t in tools if t.name == "get_object_details")

    assert tool.outputSchema is not None
    assert tool.outputSchema.get("type") == "object"
    assert "properties" in tool.outputSchema
    assert tool.outputSchema["properties"]["schema"]["type"] == "string"


@pytest.mark.asyncio
async def test_get_object_details_returns_structured_content_without_injected_null_keys():
    """Ensure structuredContent doesn't inject missing optional keys as null."""
    mock_driver = MagicMock()
    query_results = [
        [MockRow({"column_name": "id", "data_type": "uuid", "is_nullable": "NO", "column_default": None})],
        [MockRow({"constraint_name": "Account_pkey", "constraint_type": "PRIMARY KEY", "column_name": "id"})],
        [MockRow({"indexname": "Account_pkey", "indexdef": 'CREATE UNIQUE INDEX "Account_pkey" ON public."Account" USING btree (id)'})],
    ]

    with (
        patch.object(server, "get_sql_driver", AsyncMock(return_value=mock_driver)),
        patch.object(server.SafeSqlDriver, "execute_param_query", AsyncMock(side_effect=query_results)),
    ):
        result = await server.mcp.call_tool(
            "get_object_details",
            {"schema_name": "public", "object_name": "Account", "object_type": "table"},
        )

    assert isinstance(result, CallToolResult)
    assert result.structuredContent is not None
    assert result.structuredContent["basic"]["name"] == "Account"
    assert "schema" not in result.structuredContent
    assert "name" not in result.structuredContent
    assert "start_value" not in result.structuredContent
