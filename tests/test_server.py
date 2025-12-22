from __future__ import annotations

from typing import Any, Callable

import scrapinghub_mcp.server as server


class DummyMCP:
    def __init__(self, name: str) -> None:
        self.name = name
        self.tool_registry: dict[str, Callable[..., Any]] = {}

    def tool(self, name: str | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            func_name = getattr(func, "__name__", "tool")
            self.tool_registry[name or func_name] = func
            return func

        return decorator


def test_build_server_registers_tool(monkeypatch: Any) -> None:
    monkeypatch.setattr(server, "resolve_api_key", lambda: "test-key")
    built_server = server.build_server(DummyMCP)

    assert isinstance(built_server, DummyMCP)
    assert "list_projects" in built_server.tool_registry
    assert "project_summary" in built_server.tool_registry
