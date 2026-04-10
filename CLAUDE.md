# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

Deployment-only repo that wraps the [`mempalace`](https://github.com/milla-jovovich/mempalace) MCP server with an HTTP/SSE transport layer. Zero Python code in the main package — just Docker, Compose, Traefik config, and a small FastAPI OAuth server.

The `mempalace` Python package is consumed from PyPI. Do not copy or modify its source here.

## Commands

```bash
# First run — copy and fill in env
cp .env.example .env

# Start all services
docker compose up -d

# Rebuild after changing a Dockerfile or mempalace version
docker compose build --no-cache && docker compose up -d

# Rebuild only the OAuth server (auth/main.py changes)
docker compose build mempalace-oauth --no-cache && docker compose up -d mempalace-oauth

# Logs
docker compose logs -f mempalace
docker compose logs -f mempalace-oauth

# Stop
docker compose down
```

## Architecture

```
Client (claude.ai / Claude Code / any MCP client)
      ↓
  Traefik (external, traefik-public network)
      │
      ├─ PathPrefix(/oauth) || /.well-known/... || /authorize
      │       ↓
      │   mempalace-oauth :8080   (FastAPI, OAuth 2.0 server)
      │
      └─ everything else
              ↓ ForwardAuth → mempalace-oauth /oauth/verify
              ↓ (only if 200)
          mempalace :3000   (mcp-proxy → mempalace MCP server)
                ↓
          ./data/ → /mempalace/ (bind mount)
```

`mcp-proxy` spawns `python -m mempalace.mcp_server` as a subprocess and exposes it as HTTP/SSE on port 3000. Traefik routes `${DOMAIN}` → port 3000, protected by ForwardAuth.

## Services

### `mempalace-oauth` (auth/)
FastAPI OAuth 2.0 server. Handles:
- `GET  /.well-known/oauth-authorization-server` — discovery metadata
- `GET  /authorize` — login form for Authorization Code + PKCE flow (claude.ai MCP connector)
- `POST /authorize` — process login, issue auth code, redirect with `?code=...&state=...`
- `POST /oauth/token` — issue bearer token (supports `authorization_code` + `client_credentials`)
- `GET  /oauth/verify` — Traefik ForwardAuth endpoint (validates Bearer or Basic credentials)

### `mempalace`
mcp-proxy + mempalace MCP server. Protected by ForwardAuth — every request is verified before routing.

## Auth Flow

**claude.ai MCP connector** (Authorization Code + PKCE):
1. claude.ai redirects to `https://${DOMAIN}/authorize?response_type=code&client_id=...&code_challenge=...`
2. User enters `OAUTH_CLIENT_SECRET` in the login form
3. Server issues auth code → redirects to `https://claude.ai/api/mcp/auth_callback?code=...`
4. claude.ai exchanges code for bearer token via `POST /oauth/token`
5. All subsequent SSE requests carry `Authorization: Bearer <token>` → verified by ForwardAuth

**Claude Code / programmatic clients** (static bearer token):
```json
{
  "mcpServers": {
    "mempalace": {
      "type": "sse",
      "url": "https://mempalace.chars.me/sse",
      "headers": {
        "Authorization": "Bearer <OAUTH_STATIC_TOKEN>"
      }
    }
  }
}
```

> ⚠️ Claude Code's SSE transport does NOT auto-convert URL credentials (`user:pass@host`) to Basic Auth headers. Always use explicit `headers.Authorization`.

Claude Code CLI:
```bash
claude mcp add --transport sse --scope global mempalace https://mempalace.chars.me/sse \
  --header "Authorization: Bearer <OAUTH_STATIC_TOKEN>"
```

## Persistence

All palace state lives in `./data/` on the host (bind-mounted into the container). This directory is gitignored — never commit it.

| `./data/` path | Container path | Contents |
|---|---|---|
| `.mempalace/palace/` | `/mempalace/.mempalace/palace/` | ChromaDB vector store |
| `.mempalace/knowledge_graph.sqlite3` | `/mempalace/.mempalace/knowledge_graph.sqlite3` | Temporal knowledge graph |
| `.mempalace/config.json` | `/mempalace/.mempalace/config.json` | MemPalace configuration |
| `.mempalace/identity.txt` | `/mempalace/.mempalace/identity.txt` | L0 identity prompt |
| `.cache/chroma/` | `/mempalace/.cache/chroma/` | Embedding model cache (persisted across rebuilds) |

All paths are derived from `HOME=/mempalace` — mempalace uses `~/.mempalace/` by convention.

Back up `./data/` to preserve memories.

## Environment Variables

Configured in `.env` (copy from `.env.example`):

| Variable | Purpose |
|---|---|
| `DOMAIN` | Public hostname (e.g. `mempalace.chars.me`) |
| `OAUTH_CLIENT_ID` | OAuth client ID — used as username in Basic Auth and `/authorize` form |
| `OAUTH_CLIENT_SECRET` | OAuth client secret — password for all auth flows |
| `OAUTH_STATIC_TOKEN` | Optional pre-seeded bearer token — survives container restarts. Set this for Claude Code. |
| `MEMPALACE_VERSION` | PyPI version to pin (default: `latest`) |
| `MCP_PORT` | Internal mcp-proxy port (default: `3000`) |

## Networking

- Joins `traefik-public` as an **external** Docker network — Traefik must already be running
- TLS via Let's Encrypt (ACME on port 80 — must be publicly reachable)
- DNS A record for `${DOMAIN}` must point to the server's public IP
- ForwardAuth: Traefik calls `/oauth/verify` before every request to `mempalace`
- `authRequestHeaders=Authorization` is critical — without it, Traefik strips the auth header before calling verify

```
Any client → :443 → [/oauth, /.well-known, /authorize] → mempalace-oauth (no auth)
Any client → :443 → [everything else] → ForwardAuth verify → mempalace SSE
```

## Key Decisions

- **OAuth 2.0 over BasicAuth** — required for claude.ai MCP connector (uses Authorization Code + PKCE)
- **Static bearer token** (`OAUTH_STATIC_TOKEN`) — survives restarts; Claude Code uses this
- **ForwardAuth over middleware auth** — allows the OAuth server to handle all credential logic centrally
- **`userns_mode: "host"` + `user: "1000:1000"`** — required when Docker daemon has `userns-remap` enabled; matches ubuntu user UID on host so bind mount writes succeed
- **`HOME=/mempalace`** — critical env var; all mempalace `expanduser("~/.mempalace/")` paths resolve inside the bind mount
- **mcp-proxy `--host 0.0.0.0`** — required so Traefik (on a different container) can reach it; loopback default breaks routing
- **mcp-proxy does not forward env vars to subprocess** — `MEMPALACE_PALACE_PATH` env var is ignored by the mempalace subprocess; rely on `HOME`-based defaults instead

## Design Docs

- `docs/superpowers/specs/2026-04-08-http-transport-design.md` — original design spec
- `docs/superpowers/plans/2026-04-08-http-transport.md` — implementation plan
