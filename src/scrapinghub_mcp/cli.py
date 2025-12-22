from __future__ import annotations

import argparse

import structlog

from scrapinghub_mcp.server import build_server

logger = structlog.get_logger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Scrapinghub MCP stdio server.")
    parser.add_argument(
        "--allow-mutate",
        action="store_true",
        help="Enable mutating Scrapinghub API operations.",
    )
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    logger.info("server.starting", allow_mutate=args.allow_mutate)
    server = build_server(allow_mutate=args.allow_mutate)
    server.run(transport="stdio")
    logger.info("server.stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
