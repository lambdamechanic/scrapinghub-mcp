from __future__ import annotations

import os
from typing import Any, Callable, Protocol, TypeVar, cast

from fastmcp import FastMCP
from scrapinghub import ScrapinghubClient


class MCPProtocol(Protocol):
    def __init__(self, name: str) -> None: ...

    def tool(
        self, name: str | None = None
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...


MCPType = TypeVar("MCPType", bound=MCPProtocol)


API_KEY_ENV = "SCRAPINGHUB_API_KEY"


def resolve_api_key() -> str:
    api_key = os.environ.get(API_KEY_ENV)
    if not api_key:
        raise RuntimeError(f"Missing {API_KEY_ENV} environment variable.")
    return api_key


def build_server(mcp_cls: type[MCPType] | None = None) -> MCPType:
    api_key = resolve_api_key()
    cls = cast(type[MCPType], FastMCP) if mcp_cls is None else mcp_cls
    mcp = cls("scrapinghub-mcp")

    @mcp.tool()
    def list_projects() -> list[dict[str, Any]]:
        """List Scrapinghub projects for the configured API key."""
        client = cast(Any, ScrapinghubClient(api_key))
        return list(client.get_projects())

    return mcp
