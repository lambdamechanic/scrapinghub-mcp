## ADDED Requirements
### Requirement: Non-Mutating Default
By default, the server SHALL only expose non-mutating Scrapinghub API operations as defined by an explicit non-mutating whitelist mapping.

#### Scenario: Start without mutating flag
- **WHEN** a user starts the server without the mutating flag
- **THEN** only non-mutating operations are available

### Requirement: Mutating Opt-In Flag
The server SHALL require an explicit CLI flag `--allow-mutate` to enable mutating Scrapinghub API operations.

#### Scenario: Enable mutating operations
- **WHEN** a user starts the server with `--allow-mutate`
- **THEN** mutating and non-mutating operations are available

### Requirement: Mutating Classification Mapping
The server SHALL define non-mutating operations via an explicit static mapping loaded from `scrapinghub-mcp.allowlist.yaml`. Any operation not in the mapping SHALL be treated as mutating and MUST NOT be inferred dynamically.

#### Scenario: Classify mutating operations
- **WHEN** the server registers API operations
- **THEN** mutating operations are classified as any operation not listed in `scrapinghub-mcp.allowlist.yaml`

### Requirement: Allowlist File Format
The `scrapinghub-mcp.allowlist.yaml` file SHALL contain a top-level `non_mutating` list of operation identifiers, for example:
```
non_mutating:
  - projects.list
  - projects.summary
```

#### Scenario: Parse allowlist file
- **WHEN** the server loads `scrapinghub-mcp.allowlist.yaml`
- **THEN** it reads the `non_mutating` list to determine non-mutating operations

### Requirement: Allowlist File Location
The server SHALL load `scrapinghub-mcp.allowlist.yaml` from the package resources and SHALL allow a repository root (directory containing `.git`) override when present.

#### Scenario: Resolve allowlist file from package resources
- **WHEN** the server runs without a repository override file
- **THEN** it loads the packaged `scrapinghub-mcp.allowlist.yaml` resource

#### Scenario: Resolve allowlist file from repository root
- **WHEN** `scrapinghub-mcp.allowlist.yaml` exists in the repository root
- **THEN** the server loads the repository root file instead of the package resource
