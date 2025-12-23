## ADDED Requirements
### Requirement: Stdio MCP Server Entry Point
The package SHALL provide a CLI command `shub-mcp` that starts a stdio MCP server.

#### Scenario: Start server via CLI
- **WHEN** a user runs `shub-mcp`
- **THEN** the process starts a stdio MCP server and waits for requests

### Requirement: MCP Server Framework
The server SHALL use `fastmcp` v2 for MCP protocol handling.

#### Scenario: Implement server with fastmcp
- **WHEN** the MCP server is started
- **THEN** it runs using `fastmcp` v2 constructs

### Requirement: Structured Logging
The server SHALL use `structlog` for application logging.

#### Scenario: Log server events
- **WHEN** the server emits runtime logs
- **THEN** logs are produced via `structlog`

### Requirement: Modern Packaging
The project SHALL use a PEP 517 build backend with `pyproject.toml` metadata and `uv-build` as the build backend.

#### Scenario: Build package with uv
- **WHEN** a user runs `uv build`
- **THEN** a distributable package is produced using `uv-build`

### Requirement: Dependency Groups for Tooling
The project SHALL define development tooling dependencies using `dependency-groups`.

#### Scenario: Install tooling dependencies
- **WHEN** a user runs `uv sync` with the lint or dev groups
- **THEN** the tooling dependencies are installed from `dependency-groups`

### Requirement: Ruff Formatting and Linting
The project SHALL use `ruff` for Python formatting and linting with configuration in `pyproject.toml`.

#### Scenario: Run formatting and linting locally
- **WHEN** a user runs `ruff format` and `ruff check`
- **THEN** formatting and linting are executed against the codebase

### Requirement: Git Hook Tooling
The project SHALL include a git hook script that runs `ruff format` and `ruff check`, with hooks stored under a repo hook folder configured via `core.hooksPath`.

#### Scenario: Run hook checks
- **WHEN** a user runs the git hook from the configured hook folder
- **THEN** `ruff format` and `ruff check` are executed by the hook

### Requirement: Type Checking Tooling
The project SHALL use `ty` for type checking.

#### Scenario: Run type checks locally
- **WHEN** a user runs the type checking command
- **THEN** `ty` is executed against the codebase

### Requirement: CI Formatting and Linting
The repository SHALL run `ruff format --check` and `ruff check` in a GitHub workflow.

#### Scenario: CI runs formatting and linting
- **WHEN** a change is pushed to the repository
- **THEN** the GitHub workflow runs `ruff format --check` and `ruff check`

### Requirement: CI Type Checking
The repository SHALL run `ty` in a GitHub workflow.

#### Scenario: CI runs type checks
- **WHEN** a change is pushed to the repository
- **THEN** the GitHub workflow runs `ty` as part of validation
