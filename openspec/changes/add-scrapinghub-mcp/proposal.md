# Change: Add scrapinghub-mcp stdio server package

## Why
We need a minimal stdio MCP server that exposes the python-scrapinghub API with modern packaging practices and a clear safety gate for mutating operations.

## What Changes
- Add a stdio MCP server package named `scrapinghub-mcp` with a CLI entry point `shub-mcp`.
- Introduce a repo-local config file for auth (API key) with env file inclusion support.
- Separate mutating vs non-mutating API calls and require an explicit CLI flag to enable mutating operations.
- Use modern packaging with `pyproject.toml`, `uv` tooling, `uv-build` backend, and `ruff` for linting.
- Record mutating call mappings in a dedicated YAML file.
- Use `ruff` for formatting and linting (including git hooks), and run `ruff` format/lint checks in the GitHub workflow.
- Use `ty` for type checking and include it in the GitHub workflow.
- Use `python-scrapinghub`, `fastmcp` v2, and `structlog` as runtime dependencies for the server implementation.

## Impact
- Affected specs: `mcp-stdio-server`, `auth-config`, `scrapinghub-api-safety`.
- Affected code: new packaging, CLI, and MCP server implementation.
