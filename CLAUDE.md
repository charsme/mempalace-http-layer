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
Tailscale network
      ↓
  Traefik (external, traefik-public network — not managed here)
      ↓
  mempalace container :3000
  (python:3.12-slim + mempalace + mcp-proxy)
      ↓
  ./data/  →  /root/.mempalace/  (bind mount)
```

`mcp-proxy` spawns `python -m mempalace.mcp_server` as a subprocess and exposes it as HTTP/SSE on port 3000. Traefik routes `${DOMAIN}` → port 3000.

## Persistence

All palace state lives in `./data/` on the host (bind-mounted into the container). This directory is gitignored — never commit it.

| `./data/` path | Contents |
|---|---|
| `palace/` | ChromaDB vector store |
| `knowledge_graph.sqlite3` | Temporal knowledge graph |
| `config.json` | MemPalace configuration |
| `identity.txt` | L0 identity prompt |

Back up `./data/` to preserve memories.

## Environment Variables

Configured in `.env` (copy from `.env.example`):

| Variable | Purpose |
|---|---|
| `DOMAIN` | Public hostname (e.g. `mempalace.chars.me`) |
| `ACME_EMAIL` | Let's Encrypt registration email |
| `MEMPALACE_VERSION` | PyPI version to pin (default: `latest`) |
| `MCP_PORT` | Internal mcp-proxy port (default: `3000`) |

## Networking

- Joins `traefik-public` as an **external** Docker network — Traefik must already be running
- TLS via Let's Encrypt (ACME httpChallenge)
- No application-level auth — Tailscale restricts access

## Client Config (all AI tools)

```json
{
  "mcpServers": {
    "mempalace": {
      "type": "sse",
      "url": "https://mempalace.chars.me/sse"
    }
  }
}
```

## Key Decisions

- **mcp-proxy over supergateway** — stays Python, no Node.js runtime needed
- **Single container** — mcp-proxy + mempalace in one image, simpler than a sidecar
- **Bind mount over named volume** — `./data/` is easier to inspect, back up, and restore
- **No Traefik in this compose** — joins the existing `traefik-public` network instead
