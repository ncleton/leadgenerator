"""Real MCP processes preserve copied data and isolate fresh workspaces offline."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def inspect_workspace(home: Path, populate: bool = False):
    environment = dict(os.environ)
    environment["LEADGENERATOR_HOME"] = str(home)
    environment["LEADGENERATOR_DATABASE_URL"] = ""
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "leadgenerator.mcp.server"],
        env=environment,
    )
    async with (
        stdio_client(parameters) as (reader, writer),
        ClientSession(reader, writer) as session,
    ):
        await session.initialize()

        async def call(name, arguments):
            result = await session.call_tool(name, arguments)
            assert not result.is_error, result.content
            assert isinstance(result.structured_content, dict)
            return result.structured_content

        mode = await call("get_lead_interface_mode", {})
        assert mode["storage"]["private_directory"] == str(home)
        assert mode["storage"]["backend"] == "sqlite"
        if populate:
            await call(
                "create_lead_objective",
                {
                    "objective_id": "synthetic-objective",
                    "name": "Synthetic objective",
                    "description": "Exercise isolated local persistence.",
                    "instructions": "Keep facts and hypotheses separate.",
                },
            )
            await call(
                "render_lead_workspace",
                {
                    "active_objective_id": "synthetic-objective",
                    "leads": [
                        {
                            "id": "synthetic-company",
                            "company_name": "Example Industries",
                            "siren": "123456789",
                            "company_description": "Synthetic persistence fixture.",
                        }
                    ],
                },
            )
        resolution = await call(
            "resolve_lead_objective",
            {
                "message": "Trouve-moi des leads dans l'industrie",
            },
        )
        memory = await call("get_company_memory_status", {})
        matches = await call("search_remembered_companies", {"query": "Example"})
        return resolution, memory, matches


def test_mcp_restart_and_copied_workspace_preserve_data_without_global_fallback(
    tmp_path,
):
    original = tmp_path / "Original workspace/donnees-privees"
    populated = anyio.run(inspect_workspace, original, True)
    assert populated[0]["decision"]["status"] == "selected"
    assert populated[1]["stored_companies"] == 1
    assert populated[1]["stored_snapshots"] == 1

    # All server handles are closed before the folder copy, as documented.
    copied = tmp_path / "Copied workspace/donnees-privees"
    shutil.copytree(original, copied)
    restored = anyio.run(inspect_workspace, copied)
    assert restored[0]["decision"]["status"] == "selected"
    assert restored[1]["stored_companies"] == 1
    assert restored[2]["companies"][0]["lead"]["company_description"] == (
        "Synthetic persistence fixture."
    )

    fresh = anyio.run(inspect_workspace, tmp_path / "Fresh workspace/donnees-privees")
    assert fresh[0]["decision"]["status"] == "unconfigured"
    assert fresh[1]["stored_companies"] == 0
    assert fresh[2]["companies"] == []
