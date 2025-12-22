## 1. Implementation
- [ ] 1.1 Add project packaging files (`pyproject.toml`, `.python-version`, `uv.lock`) with `uv-build` backend, dependency groups, and a repo hook folder with a git hook that runs `ruff format`/`ruff check`.
- [ ] 1.2 Implement stdio MCP server with `shub-mcp` CLI entry point and add tests for CLI startup and tool registration.
- [ ] 1.3 Add repo-local config file support for API key loading (including env file inclusion) and add tests for config resolution and missing-key errors.
- [x] 1.4 Implement mutating vs non-mutating API gating with explicit `--allow-mutate` flag, load mutating mappings from `scrapinghub-mcp.allowlist.yaml`, and add tests for gating behavior and classification mapping.
- [ ] 1.5 Add GitHub workflow to run formatting, linting, and type checking (`ruff format --check`, `ruff check`, `ty`).
- [ ] 1.6 Add a live integration test that requires an auth key and exercises all non-mutating endpoints.
- [ ] 1.7 Document setup, configuration (including env file inclusion and mutations mapping), safety flag usage, git hook setup, and CI expectations.
- [ ] 1.8 Add example HTTP MCP and stdio MCP servers as sibling folders (may require moving this repo to a monorepo layout).

## 2. Validation
- [ ] 2.1 Run linting (`uv run -- ruff check .`).
- [ ] 2.2 Run tests (if added) (`uv run python -m pytest`).
- [ ] 2.3 Run `openspec validate add-scrapinghub-mcp --strict`.
