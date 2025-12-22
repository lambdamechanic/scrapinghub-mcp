from __future__ import annotations

from typing import Any, Callable, Protocol, TypeVar, cast

from fastmcp import FastMCP
from scrapinghub import ScrapinghubClient


class MCPProtocol(Protocol):
    def __init__(self, name: str) -> None: ...

    def tool(
        self, name: str | None = None
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...


MCPType = TypeVar("MCPType", bound=MCPProtocol)


def build_server(mcp_cls: type[MCPType] | None = None) -> MCPType:
    cls = cast(type[MCPType], FastMCP) if mcp_cls is None else mcp_cls
    mcp = cls("scrapinghub-mcp")

    @mcp.tool()
    def list_projects(api_key: str) -> list[dict[str, Any]]:
        """List Scrapinghub projects for the provided API key."""
        client = cast(Any, ScrapinghubClient(api_key))
        return list(client.get_projects())

    return mcp
