from __future__ import annotations

from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from aicad.core.tool_registry import build_default_registry


mcp = FastMCP("AI CAD Workbench")


@mcp.tool()
def health() -> dict[str, str]:
    """Check whether the AI CAD MCP process is available."""
    return {"status": "ok", "phase": "foundation"}


@mcp.tool()
def available_cad_tools() -> list[dict[str, object]]:
    """List the deterministic CAD tools planned by the shared registry."""
    return [asdict(spec) for spec in build_default_registry().list_specs()]


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
