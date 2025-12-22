from __future__ import annotations

from typing import Any, Callable

from scrapinghub_mcp.server import build_server


class DummyMCP:
    def __init__(self, name: str) -> None:
        self.name = name
        self.tool_registry: dict[str, Callable[..., Any]] = {}

    def tool(self, name: str | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.tool_registry[name or func.__name__] = func
            return func

        return decorator


def test_build_server_registers_tool() -> None:
    server = build_server(DummyMCP)

    assert isinstance(server, DummyMCP)
    assert "list_projects" in server.tool_registry
