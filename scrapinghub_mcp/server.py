from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from scrapinghub import ScrapinghubClient


def build_server(mcp_cls: type[FastMCP] = FastMCP) -> FastMCP:
    mcp = mcp_cls("scrapinghub-mcp")

    @mcp.tool()
    def list_projects(api_key: str) -> list[dict[str, Any]]:
        """List Scrapinghub projects for the provided API key."""
        client = ScrapinghubClient(api_key)
        return list(client.get_projects())

    return mcp
