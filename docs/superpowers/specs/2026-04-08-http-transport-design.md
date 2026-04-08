# MemPalace HTTP Transport Layer — Design Spec

**Date:** 2026-04-08
**Repo:** `mempalace-deploy` (separate from `mempalace` Python package)
**Status:** Approved

## Problem

The `mempalace` MCP server communicates over stdio — it can only be used by AI tools running on the same machine. Multiple AI clients (Claude Code, Claude Desktop, Codex, ChatGPT, etc.) need to share one palace from different machines.

## Solution

A separate deployment repo that wraps the mempalace stdio server with an HTTP/SSE transport layer using `mcp-proxy`, served behind an existing Traefik reverse proxy over Tailscale.

Zero changes to the `mempalace` Python package.

## Architecture

```
Tailscale network
      ↓
  Traefik (existing, traefik-public network)
      ↓
  mempalace container :3000
  (mempalace + mcp-proxy, single image)
      ↓
  ./data bind mount
  (ChromaDB palace + SQLite KG + config)
```

## Repo Structure

```
mempalace-http-layer/
├── Dockerfile
├── docker-compose.yml
├── traefik/
│   └── traefik.yml          # entrypoints + ACME config
├── data/                    # gitignored — palace data
│   ├── palace/              # ChromaDB files
│   ├── knowledge_graph.sqlite3
│   ├── config.json
│   └── identity.txt
├── .env.example
├── .env                     # gitignored
└── .gitignore
```

## Container

**Single service: `mempalace`**

- Base image: `python:3.12-slim`
- Installs: `mempalace` + `mcp-proxy` from PyPI
- `mcp-proxy` spawns `python -m mempalace.mcp_server` as subprocess and wraps it as HTTP/SSE on port 3000
- `MEMPALACE_PALACE_PATH` env var points to `/root/.mempalace/palace`

## Persistence

Bind mount `./data` → `/root/.mempalace/` on the container. All palace state lives in `./data/` on the host:

| Path in container | Contents |
|---|---|
| `/root/.mempalace/palace/` | ChromaDB vector store |
| `/root/.mempalace/knowledge_graph.sqlite3` | Temporal KG |
| `/root/.mempalace/config.json` | MemPalace config |
| `/root/.mempalace/identity.txt` | L0 identity file |

## Networking

- Joins existing `traefik-public` Docker network (external)
- Traefik routes `mempalace.chars.me` → container port 3000 via Docker labels
- TLS via Let's Encrypt (ACME httpChallenge)
- No auth at the application layer — Tailscale handles access control

## Environment Variables (`.env`)

| Variable | Default | Purpose |
|---|---|---|
| `DOMAIN` | `mempalace.chars.me` | Public hostname |
| `ACME_EMAIL` | — | Let's Encrypt registration email |
| `MEMPALACE_VERSION` | `latest` | PyPI version to install |
| `MCP_PORT` | `3000` | Internal port for mcp-proxy |

## Client Configuration

All AI tools use the same config:

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

## What's Not In Scope

- Multi-user / auth (Tailscale handles this)
- Including Traefik in this compose (already running separately)
- Changes to the `mempalace` Python package
