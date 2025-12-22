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
directory, then falls back to the package root (directory containing
`pyproject.toml`), and finally the repository root (directory containing
`.git`) during development. If no config file is present, it falls back to the
`SCRAPINGHUB_API_KEY` environment variable.

Use `scrapinghub-mcp.toml` with top-level `[auth]` and `[safety]` tables:

```toml
[auth]
api_key = "your-key"
# optional
# env_file = ".env"

[safety]
# optional: extend the non-mutating allowlist
# extra_non_mutating = ["projects.list"]
# optional: remove items from the allowlist (blocklist wins)
# block_non_mutating = ["projects.summary"]
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
only the packaged allowlist is used. This asymmetry is intentional so that
installed users can extend the allowlist via config without overriding the
packaged baseline.

The allowlist file itself is required even when `safety.extra_non_mutating` or
`safety.block_non_mutating` are set; config entries only adjust the packaged or
override allowlist.

Minimal allowlist file:

```yaml
non_mutating:
  - projects.list
```

The packaged allowlist lives at `scrapinghub_mcp/scrapinghub-mcp.allowlist.yaml`.

You can also extend the allowlist from `scrapinghub-mcp.toml` by setting
`safety.extra_non_mutating` to a list of additional operation identifiers. If
you need to explicitly block entries, set `safety.block_non_mutating`—blocklist
entries take precedence over the allowlist.

Example (blocklist wins):

```toml
[safety]
extra_non_mutating = ["projects.summary"]
block_non_mutating = ["projects.summary"]
```

Invalid `safety` values (wrong types or non-string list entries) will cause
startup to fail with a clear error message.

When `safety` is set, the server logs the resolved config path to help with
troubleshooting.

```yaml
non_mutating:
  - projects.list
  - projects.summary
```
