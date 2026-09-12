#!/usr/bin/env python3
"""Read-only stdio smoke test of the actual packaged Claude Desktop launcher."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def verify(package: Path) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="leadgenerator-claude-check-") as temporary:
        root = (Path(temporary) / "extension with spaces").resolve()
        root.mkdir()
        with zipfile.ZipFile(package) as bundle:
            for name in bundle.namelist():
                if not (root / name).resolve().is_relative_to(root):
                    raise ValueError("Unsafe archive member.")
            bundle.extractall(root)
        manifest = json.loads((root / "manifest.json").read_text())
        config = manifest["server"]["mcp_config"]
        node = shutil.which(config["command"])
        if node is None:
            raise RuntimeError("Node is required for the command-line smoke test.")
        args = [arg.replace("${__dirname}", str(root)) for arg in config["args"]]
        cwd = Path(temporary) / "unrelated working directory"
        cwd.mkdir()
        env = dict(os.environ)
        if os.name != "nt":
            env["PATH"] = "/usr/bin:/bin"
        parameters = StdioServerParameters(
            command=node, args=args, cwd=str(cwd), env=env
        )
        async with (
            stdio_client(parameters) as (reader, writer),
            ClientSession(
                reader, writer, extensions={"io.modelcontextprotocol/ui": {}}
            ) as session,
        ):
            with anyio.fail_after(45):
                print("Claude package: initialize", file=sys.stderr, flush=True)
                initialized = await session.initialize()
                print("Claude package: tools/list", file=sys.stderr, flush=True)
                tools = {tool.name: tool for tool in (await session.list_tools()).tools}
                for name in (
                    "get_lead_workflow",
                    "get_lead_interface_mode",
                    "get_lead_composition",
                    "search_french_companies",
                    "render_lead_explorer",
                    "render_lead_workspace",
                ):
                    if name not in tools:
                        raise RuntimeError(
                            f"Missing MCP tool: {name}. Enable chat_ui before this visual smoke test."
                        )
                for name in (
                    "get_lead_interface_mode",
                    "get_lead_workflow",
                    "get_lead_composition",
                ):
                    print(f"Claude package: {name}", file=sys.stderr, flush=True)
                    result = await session.call_tool(name, {})
                    if result.is_error or not isinstance(
                        result.structured_content, dict
                    ):
                        raise RuntimeError(f"MCP check failed: {name}")
                    content = result.structured_content
                    if (
                        name == "get_lead_composition"
                        and content.get("status") != "healthy"
                    ):
                        raise RuntimeError(
                            "Local composition needs repair before using either host."
                        )
                    if (
                        name == "get_lead_interface_mode"
                        and content["host"]["name"] != "claude"
                    ):
                        raise RuntimeError("Claude host identity was not applied.")
                    if name == "get_lead_workflow" and not content.get("markdown"):
                        raise RuntimeError("Packaged workflow instructions are absent.")
                for name in ("render_lead_explorer", "render_lead_workspace"):
                    print(
                        f"Claude package: resource for {name}",
                        file=sys.stderr,
                        flush=True,
                    )
                    uri = tools[name].meta["ui"]["resourceUri"]
                    resource = await session.read_resource(uri)
                    if (
                        not resource.contents
                        or resource.contents[0].mime_type != "text/html;profile=mcp-app"
                    ):
                        raise RuntimeError("MCP Apps HTML resource is absent.")
                    if "ui/initialize" not in resource.contents[0].text:
                        raise RuntimeError("Portable UI bridge is absent.")
                return {
                    "status": "ok",
                    "host": "claude",
                    "server": initialized.server_info.name,
                    "tools": len(tools),
                    "ui_resources_checked": 2,
                    "workflow_available": True,
                    "live_research_started": False,
                    "mutating_tools_called": False,
                }


def project_parameters(project: Path) -> StdioServerParameters:
    """Resolve the same project-scoped declaration Claude loads on session start."""
    project = project.resolve()
    config = json.loads((project / ".mcp.json").read_text())["mcpServers"][
        "leadgenerator"
    ]
    command = shutil.which(config["command"])
    if command is None:
        raise RuntimeError("The project's MCP command is not available on PATH.")
    args = [
        item.replace("${CLAUDE_PROJECT_DIR:-.}", str(project))
        for item in config["args"]
    ]
    return StdioServerParameters(
        command=command,
        args=args,
        cwd=str(project),
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(project)},
    )


async def verify_project(project: Path) -> dict[str, object]:
    """Check folder-based startup without generated packages or model requests."""
    async with (
        stdio_client(project_parameters(project)) as (reader, writer),
        ClientSession(
            reader, writer, extensions={"io.modelcontextprotocol/ui": {}}
        ) as session,
    ):
        with anyio.fail_after(45):
            await session.initialize()
            tools = {tool.name: tool for tool in (await session.list_tools()).tools}
            for name in (
                "get_lead_interface_mode",
                "get_lead_workflow",
                "get_lead_composition",
            ):
                result = await session.call_tool(name, {})
                if result.is_error or not isinstance(result.structured_content, dict):
                    raise RuntimeError(f"Project MCP check failed: {name}")
                if (
                    name == "get_lead_interface_mode"
                    and result.structured_content["host"]["name"] != "claude"
                ):
                    raise RuntimeError("Incorrect host identity.")
            for name in (
                "render_lead_explorer",
                "render_lead_workspace",
                "render_lead_objectives",
            ):
                if name not in tools:
                    raise RuntimeError(f"Missing project UI tool: {name}")
                resource = await session.read_resource(
                    tools[name].meta["ui"]["resourceUri"]
                )
                if (
                    not resource.contents
                    or resource.contents[0].mime_type != "text/html;profile=mcp-app"
                ):
                    raise RuntimeError("The project UI resource is unavailable.")
            return {
                "status": "ok",
                "installation": "project",
                "host": "claude",
                "tools": len(tools),
                "ui_tools_checked": 3,
                "generated_package_required": False,
                "mutating_tools_called": False,
            }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, nargs="?")
    parser.add_argument(
        "--project",
        type=Path,
        help="Verify the root .mcp.json instead of an extension.",
    )
    args = parser.parse_args()
    if (args.project is None) == (args.package is None):
        parser.error("Provide either an extension package or --project, not both.")
    result = (
        anyio.run(verify_project, args.project)
        if args.project
        else anyio.run(verify, args.package.resolve())
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
