from __future__ import annotations

import structlog
from dotenv import load_dotenv

from scrapinghub_mcp.server import build_server

logger = structlog.get_logger(__name__)


def main() -> int:
    load_dotenv()
    logger.info("server.starting")
    server = build_server()
    server.run(transport="stdio")
    logger.info("server.stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
