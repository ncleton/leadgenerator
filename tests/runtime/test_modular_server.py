"""MCP discovery checks for composition and customization tools."""

import asyncio

import pytest
from leadgenerator.mcp.server import server
from mcp.server.mcpserver.exceptions import ToolError


def test_mcp_discovers_modular_composition_tools():
    tools = asyncio.run(server.list_tools())
    names = {tool.name for tool in tools}
    assert {
        "get_lead_composition",
        "inspect_lead_ui_catalog",
        "preview_lead_ui_customization",
        "apply_lead_ui_customization",
        "diagnose_lead_composition",
        "restore_previous_lead_composition",
    } <= names


def test_render_tools_reference_the_selected_shell_resources():
    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    resources = {str(row.uri) for row in asyncio.run(server.list_resources())}
    for name in ("render_lead_explorer", "render_lead_workspace"):
        uri = tools[name].meta["ui"]["resourceUri"]
        assert uri in resources


def test_kernel_rejects_sensitive_mcp_call_before_provider_without_confirmation():
    with pytest.raises(ToolError, match="confirmation humaine explicite"):
        asyncio.run(
            server.call_tool(
                "sync_hubspot_contacts",
                {"leads": [], "list_name": "Synthetic", "confirm_hubspot_write": False},
            )
        )
