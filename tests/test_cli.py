from __future__ import annotations

from typing import Any

import scrapinghub_mcp.cli as cli


class DummyServer:
    def __init__(self) -> None:
        self.run_calls: list[dict[str, Any]] = []

    def run(self, *, transport: str) -> None:
        self.run_calls.append({"transport": transport})


def test_cli_starts_stdio_server(monkeypatch: Any) -> None:
    server = DummyServer()
    monkeypatch.setattr(cli, "build_server", lambda *, allow_mutate=False: server)

    result = cli.main()

    assert result == 0
    assert server.run_calls == [{"transport": "stdio"}]
