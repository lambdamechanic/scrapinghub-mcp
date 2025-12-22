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
# TODO: Expand with mutating vs non-mutating split once gating is implemented.
ALLOWED_METHODS: dict[str, str] = {
    "list_projects": "projects.list",
    "project_summary": "projects.summary",
}


def resolve_api_key() -> str:
    api_key = os.environ.get(API_KEY_ENV)
    if not api_key:
        raise RuntimeError(f"Missing {API_KEY_ENV} environment variable.")
    return api_key


def resolve_method(client: Any, path: str) -> Callable[..., Any] | None:
    current: Any = client
    for attr in path.split("."):
        current = getattr(current, attr, None)
        if current is None:
            return None
    return current if callable(current) else None


def register_scrapinghub_tools(mcp: MCPType, client: Any) -> None:
    for tool_name, method_name in ALLOWED_METHODS.items():
        method = resolve_method(client, method_name)
        if method is None:
            continue

        def tool_wrapper(*args: Any, _method: Callable[..., Any] = method, **kwargs: Any) -> Any:
            result = _method(*args, **kwargs)
            if isinstance(result, (str, bytes, dict)):
                return result
            if hasattr(result, "__iter__"):
                return list(result)
            return result

        mcp.tool(name=tool_name)(tool_wrapper)


def build_server(mcp_cls: type[MCPType] | None = None) -> MCPType:
    api_key = resolve_api_key()
    cls = cast(type[MCPType], FastMCP) if mcp_cls is None else mcp_cls
    mcp = cls("scrapinghub-mcp")
    client = cast(Any, ScrapinghubClient(api_key))
    register_scrapinghub_tools(mcp, client)
    return mcp
