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

[safety]
# optional: extend the non-mutating allowlist
# extra_non_mutating = ["projects.list"]
```

If `env_file` is set, the server loads it and reads `SCRAPINGHUB_API_KEY` from the
process environment. The server does not auto-load `.env` files unless they are
listed under `auth.env_file`.

## Safety gating

By default, `shub-mcp` only exposes non-mutating operations. To allow mutating
operations, start the server with:

```bash
shub-mcp --allow-mutate
```

Non-mutating operations are whitelisted in `scrapinghub-mcp.allowlist.yaml`,
which is bundled with the package. During development, you can override it by
placing a `scrapinghub-mcp.allowlist.yaml` file at the repository root
(directory containing `.git`). When the override is present, it takes
precedence over the packaged file. If you are running outside a git repository,
only the packaged allowlist is used.

You can also extend the allowlist from `scrapinghub-mcp.toml` by setting
`safety.extra_non_mutating` to a list of additional operation identifiers.

```yaml
non_mutating:
  - projects.list
  - projects.summary
```
