from __future__ import annotations

import argparse
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


def test_cli_passes_allow_mutate(monkeypatch: Any) -> None:
    server = DummyServer()
    captured: dict[str, bool] = {}

    def fake_build_server(*, allow_mutate: bool = False) -> DummyServer:
        captured["allow_mutate"] = allow_mutate
        return server

    monkeypatch.setattr(cli, "build_server", fake_build_server)
    monkeypatch.setattr(cli, "parse_args", lambda: argparse.Namespace(allow_mutate=True))

    result = cli.main()

    assert result == 0
    assert captured["allow_mutate"] is True


def test_parse_args_defaults_disallow_mutate() -> None:
    args = cli.parse_args([])

    assert args.allow_mutate is False


def test_parse_args_allows_mutate_flag() -> None:
    args = cli.parse_args(["--allow-mutate"])

    assert args.allow_mutate is True
