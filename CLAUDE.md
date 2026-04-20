# CLAUDE.md — Security Report Tool

## Purpose

Generates a CSV of all Meterian projects/branches with security advisory counts and status, querying the Meterian REST API.

---

## API Reference

**Base URL:** `https://www.meterian.com`  
**Auth header:** `Authorization: Token {token}` — capital T, no "Bearer"  
**Swagger spec:** `https://www.meterian.com/documentation/v2/api-docs`

### Endpoints used

#### `GET /api/v2/reports?sinceDaysAgo={days}`
Returns the list of projects scanned within the given number of days.

Response is a JSON array. Each element shape:
```json
{
  "uuid": "...",
  "name": "github:org/repo",
  "branch": "main",
  "tags": "tag1,tag2,",
  "outcome": "PASS|FAIL|UNDECLARED",
  "status": "OK|FAIL|...",
  "timestamp": 1776676011804
}
```
- `tags` is a **comma-separated string** (not an array), may have a trailing comma — strip it
- `timestamp` here is **milliseconds epoch** — not used in output (full report timestamp is used instead)
- `url` is **not present** — comes from the full report

#### `GET /api/v1/reports/{uuid}/full?branch={branch}`
Returns the full security report for a project/branch.

Key fields used:
```json
{
  "outcome": "PASS|FAIL|UNDECLARED",
  "tool": "BOSS|BOSSC|ISAAC|SELENE|SASHA|OTHER",
  "timestamp": {
    "year": 2026, "monthValue": 4, "dayOfMonth": 20,
    "hour": 9, "minute": 6, "second": 51, ...
  },
  "project": {
    "url": "https://github.com/org/repo?account=..."
  },
  "security": {
    "assessments": [
      { "reports": [ { "advices": [ { "severity": "CRITICAL|HIGH|MEDIUM|LOW" } ] } ] }
    ]
  }
}
```
- `timestamp` is a **Java LocalDateTime dict**, not an ISO string
- `project.url` contains a `?account=...` query string — strip it with `.split("?")[0]`
- Advisory counts must be **computed client-side** by iterating `security.assessments[].reports[].advices[]`

#### `GET /api/v1/accounts/me/tags/{tag}`
Returns project UUIDs associated with a tag:
```json
{ "projects": ["uuid1", "uuid2"] }
```
Used to filter the project list when `--tag` is specified. No validation — if the tag returns no results, the filtered list will simply be empty.

---

## Design Decisions

- **Package manager:** UV (`uv sync`, `uv run report.py`). `requirements.txt` is also maintained for pip users.
- **Date format:** `YYYY/MM/DD HH:MM` (no seconds)
- **CSV sort order:** Descending by `last_updated`
- **Progress output:** Single overwriting line via `\r`, padded to 120 chars to clear previous content
- **Rate limiting:** 0.5s sleep between each full report fetch
- **Tool filter:** Applied client-side after fetching the full report (API has no server-side tool filter)
- **Tags display:** The raw string from the v2 response, trailing comma stripped. Not derived from `--tag` argument.
