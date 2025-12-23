## Context
We are creating a minimal stdio MCP server that wraps python-scrapinghub with modern Python packaging. The server must be safe by default and require an explicit opt-in flag before exposing mutating operations.

## Goals / Non-Goals
- Goals:
  - Provide a `shub-mcp` CLI that starts a stdio MCP server.
  - Package `scrapinghub-mcp` using `pyproject.toml` with `uv-build` backend.
  - Use `ruff` for linting and `uv` dependency groups for dev tooling.
  - Load auth from a repo-local config file (API key only).
  - Gate mutating API calls behind an explicit CLI flag.
- Non-Goals:
  - Implement a full configuration UI or multiple auth schemes.
  - Add a web server or non-stdio transport.

## Decisions
- Decision: Use `uv-build` as the PEP 517 backend and `uv` for build/publish.
  - Why: Aligns with modern Astral tooling and supports `uv build`/`uv publish`.
- Decision: Use `fastmcp` v2 for the stdio MCP server implementation.
  - Why: Provides a modern MCP server framework with a stable v2 API.
- Decision: Use `ty` for type checking and enforce it in CI.
  - Why: Provides fast, modern type checking aligned with the Astral tooling stack.
- Decision: Use `structlog` for application logging.
  - Why: Structured logs simplify debugging and operational visibility.
- Decision: Provide a repo-local config file for the API key.
  - Why: Keeps secrets scoped to a project and avoids global configuration.
- Decision: Use stdlib `tomllib` for parsing the repo-local config file.
  - Why: Python 3.11+ includes TOML parsing without extra dependencies.
- Decision: Keep CLI argument parsing via `fastmcp` defaults (cyclopts), not `typer`.
  - Why: Avoids an extra dependency and aligns with the MCP framework's tooling.
- Decision: Default to non-mutating operations; enable all API methods only with an explicit CLI flag.
  - Why: Reduces accidental destructive actions and keeps behavior explicit.

## Risks / Trade-offs
- Users must opt-in to mutating APIs, which may require updates to their workflows.
- Repo-local config requires documentation so users know where to place secrets.

## Migration Plan
- New package only; no existing consumers to migrate.

## Open Questions
- None.
