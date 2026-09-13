#!/usr/bin/env python3
"""Verify fresh onboarding through real MCP without touching client data/network."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def verify() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="leadgenerator-onboarding-") as directory:
        environment = dict(os.environ)
        environment["LEADGENERATOR_HOME"] = str(Path(directory) / "donnees-privees")
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
                if result.is_error or not isinstance(result.structured_content, dict):
                    raise RuntimeError(f"Onboarding check failed: {name}")
                return result.structured_content

            mode = await call("get_lead_interface_mode", {})
            memory = await call("get_company_memory_status", {})
            resolution = await call(
                "resolve_lead_objective",
                {"message": "Trouve-moi des leads dans l'industrie"},
            )
            if (
                Path(mode["storage"]["private_directory"]).resolve()
                != Path(environment["LEADGENERATOR_HOME"]).resolve()
                or memory["backend"] != "sqlite"
                or memory["stored_companies"] != 0
                or resolution["decision"]["status"] != "unconfigured"
                or resolution["research_authorized"] is not False
                or not resolution["decision"]["clarification_prompt"]
            ):
                raise RuntimeError(
                    "Fresh installation must request its first objective."
                )
            return {
                "onboarding_verified": True,
                "private_data_touched": False,
                "backend": "sqlite",
            }


if __name__ == "__main__":
    print(json.dumps(anyio.run(verify)))
