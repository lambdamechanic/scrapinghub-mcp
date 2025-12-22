# scrapinghub-mcp

## Installed usage

When installed via `pip` or `uv`, the server looks for `scrapinghub-mcp.toml` in the
current working directory. If no config file is present, it falls back to the
`SCRAPINGHUB_API_KEY` environment variable.

Use `scrapinghub-mcp.toml` with an `[auth]` table:

```toml
[auth]
api_key = "your-key"
# optional
# env_file = ".env"
```

If `env_file` is set, the server loads it and reads `SCRAPINGHUB_API_KEY` from the
process environment.
