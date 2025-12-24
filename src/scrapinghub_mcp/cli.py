from __future__ import annotations

import argparse
import logging
import sys

import structlog

from scrapinghub_mcp.server import ConfigError, build_server

logger = structlog.get_logger(__name__)


def _configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Scrapinghub MCP stdio server.")
    parser.add_argument(
        "--allow-mutate",
        action="store_true",
        help="Enable mutating Scrapinghub API operations.",
    )
    return parser.parse_args(argv)


def main() -> int:
    _configure_logging()
    args = parse_args()
    logger.info("server.starting", allow_mutate=args.allow_mutate)
    try:
        server = build_server(allow_mutate=args.allow_mutate)
    except ConfigError as exc:
        logger.warning("server.config.missing", message=str(exc))
        return 1
    server.run(transport="stdio")
    logger.info("server.stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
