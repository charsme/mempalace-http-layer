# mempalace-http-layer

HTTP/SSE transport layer for the [mempalace](https://github.com/milla-jovovich/mempalace) MCP memory server.

Wraps `mempalace` with `mcp-proxy` behind Traefik and OAuth 2.0, making it accessible to any MCP client over the network — including claude.ai and Claude Code.

## What it does

- Exposes mempalace as an HTTP/SSE MCP endpoint at your domain
- Protects it with OAuth 2.0 (Authorization Code + PKCE for claude.ai, static bearer token for Claude Code)
- Shares a single palace across multiple AI clients simultaneously

## Stack

- **mempalace** — MCP memory server (from PyPI)
- **mcp-proxy** — wraps the stdio MCP server as HTTP/SSE
- **FastAPI OAuth server** — issues and verifies tokens
- **Traefik** — reverse proxy with ForwardAuth (external, not managed here)
- **Docker Compose** — orchestrates the two services

## Quick start

```bash
cp .env.example .env
# Fill in DOMAIN, OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET, OAUTH_STATIC_TOKEN
docker compose up -d
```

Requires an existing Traefik instance on the `traefik-public` Docker network with TLS via Let's Encrypt.

## Connect Claude Code

```bash
claude mcp add --transport sse --scope global mempalace https://your.domain/sse \
  --header "Authorization: Bearer <OAUTH_STATIC_TOKEN>"
```

## Connect claude.ai

Add your SSE URL as a remote MCP server in claude.ai settings. It will redirect to `/authorize` for OAuth login — enter your `OAUTH_CLIENT_SECRET` when prompted.

## Documentation

See [CLAUDE.md](CLAUDE.md) for full architecture, auth flows, environment variables, and deployment decisions.
