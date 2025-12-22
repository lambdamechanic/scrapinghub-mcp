# scrapinghub-mcp

## Installed usage

When installed via `pip` or `uv`, start the stdio MCP server with `shub-mcp`
(the CLI entry point for the `scrapinghub-mcp` server over stdio).
We expect installed usage; repo-local behavior is dev scaffolding only.

```bash
export SCRAPINGHUB_API_KEY="..."
shub-mcp
```

The server first looks for `scrapinghub-mcp.toml` in the current working
directory, then falls back to package or repo roots during development. If no
config file is present, it falls back to the `SCRAPINGHUB_API_KEY` environment
variable.

Use `scrapinghub-mcp.toml` with an `[auth]` table:

```toml
[auth]
api_key = "your-key"
# optional
# env_file = ".env"
```

If `env_file` is set, the server loads it and reads `SCRAPINGHUB_API_KEY` from the
process environment. The server does not auto-load `.env` files unless they are
listed under `auth.env_file`.
