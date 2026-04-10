# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

Deployment-only repo that wraps the [`mempalace`](https://github.com/milla-jovovich/mempalace) MCP server with an HTTP/SSE transport layer. Zero Python code — just Docker, Compose, and Traefik config.

The `mempalace` Python package is consumed from PyPI. Do not copy or modify its source here.

## Commands

```bash
# First run — copy and fill in env
cp .env.example .env

# Start
docker compose up -d

# Rebuild after changing Dockerfile or mempalace version
docker compose build --no-cache && docker compose up -d

# Logs
docker compose logs -f mempalace

# Stop
docker compose down
```

## Architecture

```
Any client (with BasicAuth credentials)
      ↓
  Traefik (external, traefik-public network — not managed here)
      ↓
  mempalace container :3000
  (python:3.12-slim + mempalace + mcp-proxy, runs as UID 1000)
      ↓
  ./data/  →  /mempalace/  (bind mount)
```

`mcp-proxy` spawns `python -m mempalace.mcp_server` as a subprocess and exposes it as HTTP/SSE on port 3000. Traefik routes `${DOMAIN}` → port 3000.

## Persistence

All palace state lives in `./data/` on the host (bind-mounted into the container). This directory is gitignored — never commit it.

| `./data/` path | Container path | Contents |
|---|---|---|
| `.mempalace/palace/` | `/mempalace/.mempalace/palace/` | ChromaDB vector store |
| `.mempalace/knowledge_graph.sqlite3` | `/mempalace/.mempalace/knowledge_graph.sqlite3` | Temporal knowledge graph |
| `.mempalace/config.json` | `/mempalace/.mempalace/config.json` | MemPalace configuration |
| `.mempalace/identity.txt` | `/mempalace/.mempalace/identity.txt` | L0 identity prompt |
| `.cache/chroma/` | `/mempalace/.cache/chroma/` | Embedding model cache (persisted across rebuilds) |

All paths are derived from `HOME=/mempalace` — mempalace uses `~/.mempalace/` by convention. `KnowledgeGraph.__init__` creates the directory automatically on first run.

Back up `./data/` to preserve memories.

## Environment Variables

Configured in `.env` (copy from `.env.example`):

| Variable | Purpose |
|---|---|
| `DOMAIN` | Public hostname (e.g. `mempalace.chars.me`) |
| `MEMPALACE_VERSION` | PyPI version to pin (default: `latest`) |
| `MCP_PORT` | Internal mcp-proxy port (default: `3000`) |
| `MEMPALACE_AUTH` | Traefik BasicAuth credential — `user:$$bcrypt_hash` (generate below) |

Generate `MEMPALACE_AUTH`:
```bash
htpasswd -nB youruser | sed 's/\$/$$/g'
```

## Networking

- Joins `traefik-public` as an **external** Docker network — Traefik must already be running
- TLS via Let's Encrypt (ACME httpChallenge on port 80 — must be publicly reachable)
- DNS A record for `${DOMAIN}` should point to the server's **public IP**
- Auth: HTTP Basic Auth via Traefik middleware (`MEMPALACE_AUTH` env var) — open to any client
- Port 80 serves the ACME challenge only; mempalace has no port 80 router

```
Any client → :80  → ACME challenge only
Any client → :443 → BasicAuth → mcp-proxy → mempalace
```

## Client Config (all AI tools)

Embed credentials in the URL:

```json
{
  "mcpServers": {
    "mempalace": {
      "type": "sse",
      "url": "https://youruser:yourpassword@mempalace.chars.me/sse"
    }
  }
}
```

Claude Code CLI:
```bash
claude mcp add --transport sse --scope global mempalace https://youruser:yourpassword@mempalace.chars.me/sse
```

## Key Decisions

- **mcp-proxy over supergateway** — stays Python, no Node.js runtime needed
- **Single container** — mcp-proxy + mempalace in one image, simpler than a sidecar
- **Bind mount over named volume** — `./data/` is easier to inspect, back up, and restore
- **No Traefik in this compose** — joins the existing `traefik-public` network instead

## Design Docs

- `docs/superpowers/specs/2026-04-08-http-transport-design.md` — original design spec with problem statement and architecture decisions
- `docs/superpowers/plans/2026-04-08-http-transport.md` — implementation plan
