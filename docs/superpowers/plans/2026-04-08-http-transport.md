# MemPalace HTTP Transport Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a Docker Compose deployment repo that wraps the `mempalace` stdio MCP server with HTTP/SSE transport via `mcp-proxy`, routed through an existing Traefik reverse proxy.

**Architecture:** A single `mempalace` container installs `mempalace` + `mcp-proxy` from PyPI. `mcp-proxy` spawns the stdio server as a subprocess and exposes it as HTTP/SSE on port 3000. Traefik (already running in `traefik-public` network) routes `mempalace.chars.me` to that port. Palace data persists via a `./data` bind mount.

**Tech Stack:** Docker, Docker Compose v2, mcp-proxy (PyPI), mempalace (PyPI), Traefik (external)

---

## File Map

| File | Purpose |
|---|---|
| `.gitignore` | Exclude `data/` and `.env` from version control |
| `.env.example` | Template for required environment variables |
| `data/.gitkeep` | Ensures `data/` directory exists in the repo |
| `Dockerfile` | Builds image with mempalace + mcp-proxy |
| `docker-compose.yml` | Service definition, volumes, Traefik labels, external network |

---

### Task 1: Repo skeleton

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `data/.gitkeep`

- [ ] **Step 1: Verify git is initialized**

```bash
git -C . rev-parse --git-dir
```
Expected: `.git`

- [ ] **Step 2: Create `.gitignore`**

```
# Environment
.env

# Palace data — never commit memories
data/*
!data/.gitkeep
```

- [ ] **Step 3: Create `.env.example`**

```
# Public hostname routed by Traefik
DOMAIN=mempalace.chars.me

# PyPI version to install — use "latest" for newest, or pin e.g. "3.0.0"
MEMPALACE_VERSION=latest

# Internal port for mcp-proxy (must match Traefik label)
MCP_PORT=3000
```

- [ ] **Step 4: Create `data/.gitkeep`**

Create an empty file at `data/.gitkeep`. This ensures the `data/` directory is tracked in git so the bind mount path exists after a fresh clone.

- [ ] **Step 5: Verify gitignore is working**

```bash
cp .env.example .env
echo "test" > data/palace_test.txt
git status
```

Expected output: `.env` and `data/palace_test.txt` are **not** listed as untracked. Only `.gitignore`, `.env.example`, and `data/.gitkeep` should appear.

```bash
rm .env data/palace_test.txt
```

- [ ] **Step 6: Commit**

```bash
git add .gitignore .env.example data/.gitkeep
git commit -m "chore: add repo skeleton, gitignore, and env template"
```

---

### Task 2: Dockerfile

**Files:**
- Create: `Dockerfile`

- [ ] **Step 1: Verify build fails without Dockerfile**

```bash
docker build . 2>&1 | head -5
```
Expected: error about no Dockerfile found (confirms we're starting from scratch).

- [ ] **Step 2: Create `Dockerfile`**

```dockerfile
FROM python:3.12-slim

ARG MEMPALACE_VERSION=latest

# Install mcp-proxy first (stable), then mempalace at requested version
RUN pip install --no-cache-dir mcp-proxy \
    && if [ "$MEMPALACE_VERSION" = "latest" ]; then \
         pip install --no-cache-dir mempalace; \
       else \
         pip install --no-cache-dir "mempalace==${MEMPALACE_VERSION}"; \
       fi

ENV MEMPALACE_PALACE_PATH=/root/.mempalace/palace

EXPOSE 3000

CMD ["mcp-proxy", "--port", "3000", "--", "python", "-m", "mempalace.mcp_server"]
```

- [ ] **Step 3: Build and verify it succeeds**

```bash
docker build -t mempalace-test .
```
Expected: `Successfully built` with no errors.

- [ ] **Step 4: Verify mcp-proxy is callable inside the image**

```bash
docker run --rm mempalace-test mcp-proxy --help 2>&1 | head -10
```
Expected: usage/help output from mcp-proxy (not "command not found").

- [ ] **Step 5: Verify mempalace is importable**

```bash
docker run --rm mempalace-test python -c "import mempalace; print(mempalace.__version__)"
```
Expected: a version string like `3.0.0`.

- [ ] **Step 6: Clean up test image**

```bash
docker rmi mempalace-test
```

- [ ] **Step 7: Commit**

```bash
git add Dockerfile
git commit -m "feat: add Dockerfile with mempalace and mcp-proxy"
```

---

### Task 3: Docker Compose

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Verify compose config fails without file**

```bash
docker compose config 2>&1 | head -5
```
Expected: error about no compose file found.

- [ ] **Step 2: Create `docker-compose.yml`**

```yaml
services:
  mempalace:
    build:
      context: .
      args:
        MEMPALACE_VERSION: ${MEMPALACE_VERSION:-latest}
    container_name: mempalace
    restart: unless-stopped
    environment:
      - MEMPALACE_PALACE_PATH=/root/.mempalace/palace
    volumes:
      - ./data:/root/.mempalace
    expose:
      - "${MCP_PORT:-3000}"
    networks:
      - traefik-public
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.mempalace.rule=Host(`${DOMAIN}`)"
      - "traefik.http.routers.mempalace.entrypoints=websecure"
      - "traefik.http.routers.mempalace.tls.certresolver=letsencrypt"
      - "traefik.http.services.mempalace.loadbalancer.server.port=${MCP_PORT:-3000}"

networks:
  traefik-public:
    external: true
```

- [ ] **Step 3: Create `.env` from example and validate compose resolves**

```bash
cp .env.example .env
docker compose config
```
Expected: full resolved YAML printed with no errors. Verify:
- `container_name: mempalace`
- volume maps `./data` to `/root/.mempalace`
- network `traefik-public` shows `external: true`
- Traefik label shows `Host(\`mempalace.chars.me\`)`

- [ ] **Step 4: Build via compose**

```bash
docker compose build
```
Expected: `Successfully built` — same result as Task 2 Step 3, but through compose.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add docker-compose with Traefik labels and persistent data volume"
```

---

### Task 4: Smoke test

> Run this on the target server where Traefik + Tailscale are already running.
> On a fresh machine without Traefik, skip Step 3 and use `curl localhost:3000` instead.

**Files:** none — validation only

- [ ] **Step 1: Copy env and start the service**

```bash
cp .env.example .env
# Edit .env — set DOMAIN to your actual Tailscale hostname if different
docker compose up -d
```

- [ ] **Step 2: Check the container started cleanly**

```bash
docker compose logs mempalace
```
Expected: logs from mcp-proxy showing it started and spawned the mempalace subprocess. No `error` or `exit` lines.

- [ ] **Step 3: Verify the SSE endpoint is reachable**

From a machine on the Tailscale network:
```bash
curl -N https://mempalace.chars.me/sse
```
Expected: an open SSE stream (connection stays open, no immediate error). Press Ctrl+C to cancel.

- [ ] **Step 4: Verify palace data directory is being written to**

```bash
ls -la data/
```
Expected: `palace/` directory exists and has files inside it (ChromaDB creates these on first run).

- [ ] **Step 5: Commit smoke test result as a note**

If anything needed fixing in `.env` or labels, commit the fix:
```bash
git add -p  # stage only intentional changes
git commit -m "fix: adjust <whatever needed fixing> after smoke test"
```
If nothing needed fixing, no commit needed.

---

## Client Config Reference

Once the server is running, configure each AI tool:

**Claude Code / Claude Desktop** (`.claude/settings.json` or MCP settings):
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

**ChatGPT / other tools** — same URL: `https://mempalace.chars.me/sse`
