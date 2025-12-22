## ADDED Requirements
### Requirement: Repo-Local Auth Config
The server SHALL load the Scrapinghub API key from a `scrapinghub-mcp.toml` configuration file using stdlib `tomllib`.

#### Scenario: Load API key from config
- **WHEN** the server starts
- **THEN** it reads the API key from `scrapinghub-mcp.toml` using stdlib `tomllib`

### Requirement: Config Schema
The `scrapinghub-mcp.toml` file SHALL support an `[auth]` table with `api_key` and optional `env_file` entries.

#### Scenario: Read auth schema
- **WHEN** the server parses `scrapinghub-mcp.toml`
- **THEN** it reads `auth.api_key` and `auth.env_file` if present

### Requirement: Env File Inclusion
When `auth.env_file` is set, the server SHALL load environment variables from that file and use `SCRAPINGHUB_API_KEY` to resolve the API key if `auth.api_key` is not set.

#### Scenario: Load API key from env file
- **WHEN** `auth.env_file` is set and `auth.api_key` is absent
- **THEN** the server loads the env file and resolves `SCRAPINGHUB_API_KEY` from the environment

### Requirement: Config File Location
The server SHALL look for `scrapinghub-mcp.toml` in the current working directory first, then the package root (directory containing the package's `pyproject.toml`), and fall back to the repository root (directory containing `.git`) if not found.

#### Scenario: Resolve config from working directory
- **WHEN** `scrapinghub-mcp.toml` exists in the current working directory
- **THEN** the server loads that file and does not fall back to parent directories

#### Scenario: Resolve config from package root
- **WHEN** `scrapinghub-mcp.toml` exists in the package root but not the working directory
- **THEN** the server loads that file and does not fall back to the repository root

#### Scenario: Resolve config from repository root
- **WHEN** `scrapinghub-mcp.toml` does not exist in the working directory or package root but exists in the repository root
- **THEN** the server loads the repository root file

### Requirement: Missing Config Handling
When the config file is missing, the server SHALL fall back to `SCRAPINGHUB_API_KEY`. When both the config file and `SCRAPINGHUB_API_KEY` are missing, the server SHALL fail with a clear error that includes a link to the configuration documentation.

#### Scenario: Resolve API key from env without config
- **WHEN** the config file is missing but `SCRAPINGHUB_API_KEY` is set
- **THEN** startup continues using the environment variable

#### Scenario: Missing API key
- **WHEN** the config file is missing and `SCRAPINGHUB_API_KEY` is not set
- **THEN** startup fails with a clear error message that links to `https://github.com/lambdamechanic/scrapinghub-mcp`

### Requirement: Allowlist Extensions
The `scrapinghub-mcp.toml` file SHALL support a `[safety]` table with an optional `extra_non_mutating` list of operation identifiers to extend the packaged allowlist.

#### Scenario: Extend non-mutating allowlist
- **WHEN** `safety.extra_non_mutating` is set in `scrapinghub-mcp.toml`
- **THEN** the server adds those operations to the non-mutating allowlist

### Requirement: Allowlist Blocklist
The `scrapinghub-mcp.toml` file SHALL support a `[safety]` table with an optional `block_non_mutating` list of operation identifiers to remove entries from the non-mutating allowlist.

#### Scenario: Block non-mutating allowlist entries
- **WHEN** `safety.block_non_mutating` is set in `scrapinghub-mcp.toml`
- **THEN** the server removes those operations from the non-mutating allowlist
