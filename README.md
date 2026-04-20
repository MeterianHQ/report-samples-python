# Meterian Security Report Tool

Generates a CSV report of all projects and branches in your Meterian account, including security advisory counts and status.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- A Meterian API token (requires a paid plan — generate one at https://meterian.com/account/#tokens)

## Setup

With uv (recommended):

```bash
uv sync
```

With pip:

```bash
pip install -r requirements.txt
```

## Usage

```bash
uv run report.py [OPTIONS]
```

Set your API token via environment variable:

```bash
export METERIAN_API_TOKEN=your-token-here
uv run report.py
```

Or pass it directly:

```bash
uv run report.py --token your-token-here
```

## Options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--token` | `-t` | `$METERIAN_API_TOKEN` | API token |
| `--days` | `-d` | `30` | Only include projects updated within this many days |
| `--tag` | `-g` | _(all projects)_ | Filter projects by tag |
| `--tool` | `-T` | _(all tools)_ | Filter by tool: `BOSS`, `BOSSC`, `ISAAC`, `SELENE`, `SASHA`, `OTHER` |
| `--output` | `-o` | `meterian_report.csv` | Output CSV file path |
| `--log` | `-l` | `warning` | Log level: `debug`, `info`, `warning`, `error`, `critical` |

## Examples

```bash
# All projects updated in the last 90 days
uv run report.py

# Last 30 days only
uv run report.py --days 30

# Filter by tag, write to a custom file
uv run report.py --tag my-team --output my-team.csv

# Filter by tool
uv run report.py --tool BOSS

# Combine filters
uv run report.py --tag production --tool ISAAC --days 60 --output prod.csv

# Debug mode
uv run report.py --log debug
```

## Output

The CSV contains one row per project/branch combination:

| Column | Description |
|--------|-------------|
| `url` | Project repository URL |
| `branch` | Branch name |
| `status` | Security outcome: `PASS`, `FAIL`, or `UNDECLARED` |
| `critical` | Number of CRITICAL advisories |
| `high` | Number of HIGH advisories |
| `medium` | Number of MEDIUM advisories |
| `low` | Number of LOW advisories |
| `tags` | Associated tags  |
| `last_updated` | Timestamp of the last report (UTC) |
