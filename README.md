# wunder-user-mcp

An [MCP](https://modelcontextprotocol.io) server that exposes the **Wunder Mobility v2
end-user (User) API** as tools. It lets an MCP client (Claude, etc.) browse vehicles,
inspect and operate rentals, and create rentals/reservations on behalf of a single
signed-in end user.

Authentication is handled entirely from a **refresh token** you provide via env var —
the server exchanges it for short-lived access tokens and refreshes them automatically,
so tool callers never deal with tokens.

## Tools

| Tool | What it does | Underlying endpoint |
|------|--------------|---------------------|
| `get_vehicles` | List available vehicles. With a `latitude`/`longitude`, annotates each vehicle with distance from the user and sorts ascending. | `GET /vehicles` |
| `get_active_rental` | Return the user's ongoing rental(s) (`ACTIVE` / `RESERVATION`). | `GET /rentals` |
| `rental_command` | Operate a rental: `START`, `PARK`, `DRIVE`, `END`, `OPEN_TAILBOX`, `RENEW_RESERVATION`, … | `POST /rentals/{id}/operation` |
| `create_rental` | Create a rental in `RESERVATION` or `ACTIVE` state from a `vehicle_id` or `vehicle_code`. | `POST /rentals` |

## Configuration

All configuration is via environment variables (see `.env.example`):

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `WUNDER_REFRESH_TOKEN` | ✅ | — | Long-lived refresh token for the end user. |
| `WUNDER_TENANT` | ✅ | — | Tenant short-code used in the API URL path. |
| `WUNDER_BASE_URL` | | `https://go.api.gourban.services/v1` | API gateway base URL. |
| `WUNDER_BRANCH_ID` | | — | Default branch id for vehicle/rental calls. |
| `WUNDER_DEFAULT_RADIUS_MI` | | `5` | Radius (miles) used by `get_vehicles` when a location is given without a radius. |
| `WUNDER_HTTP_TIMEOUT` | | `30` | Per-request timeout in seconds. |

### Getting a refresh token

Sign in once via the Wunder Authentication API (e.g. `POST /{tenant}/auth/sign-in-email`,
`/sign-in-phone-number`, or `/sign-in-api-client`) and copy the `refreshToken` from the
response into `WUNDER_REFRESH_TOKEN`.

## Run

Run straight from the GitHub repo — no clone and no PyPI publish required (`uvx` builds
from the Git source):

```bash
uvx --from git+https://github.com/slettmayer/wunder-user-mcp wunder-user-mcp
```

Pin a branch, tag, or commit for stability by appending `@<ref>`:

```bash
uvx --from git+https://github.com/slettmayer/wunder-user-mcp@main wunder-user-mcp
```

`uvx` caches the build, so to pick up new commits on a moving ref (e.g. `@main`) add
`--refresh`:

```bash
uvx --refresh --from git+https://github.com/slettmayer/wunder-user-mcp@main wunder-user-mcp
```

From a local checkout (development):

```bash
uv run wunder-user-mcp        # editable install, reflects local edits
uvx --from . wunder-user-mcp  # build from the current directory
```

In all cases `WUNDER_REFRESH_TOKEN` and `WUNDER_TENANT` must be set in the environment
(see [Configuration](#configuration)). The server speaks MCP over **stdio**.

## MCP client configuration

```json
{
  "mcpServers": {
    "wunder-user": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/slettmayer/wunder-user-mcp",
        "wunder-user-mcp"
      ],
      "env": {
        "WUNDER_REFRESH_TOKEN": "<refresh-token>",
        "WUNDER_TENANT": "<tenant-code>",
        "WUNDER_BASE_URL": "https://go-staging.api.gourban.services/v1",
        "WUNDER_BRANCH_ID": "<optional-branch-id>"
      }
    }
  }
}
```

`WUNDER_BASE_URL` defaults to production (`https://go.api.gourban.services/v1`); the
value above targets **staging** (`go-staging`). Set it to match your tenant's environment
— a staging tenant on the production host returns `404`. To pin a ref, append `@<ref>` to
the URL, e.g. `git+https://github.com/slettmayer/wunder-user-mcp@main`.

## Development

```bash
uv sync            # install deps (incl. dev group)
uv run pytest      # offline unit tests (geo + JWT exp parsing)
uv run ruff check  # lint
```

## Notes / caveats

- The vehicle **position field path** used for distance calculation is detected
  best-effort (`lat`/`lng`, `latitude`/`longitude`, or a nested `position`/`location`).
  If a tenant's response uses different field names, extend `geo.py`.
- `operation_type` in `rental_command` is passed through to the API, so tenant-specific
  operations beyond the documented set keep working.
- Rental creation and `END` are high-impact: they can trigger vehicle commands, payment
  authorization/capture, deposits, and invoices.
