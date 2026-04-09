FROM python:3.12-slim

ARG MEMPALACE_VERSION=latest

# Install mcp-proxy first (stable), then mempalace at requested version
RUN pip install --no-cache-dir mcp-proxy \
    && if [ "$MEMPALACE_VERSION" = "latest" ]; then \
         pip install --no-cache-dir mempalace; \
       else \
         pip install --no-cache-dir "mempalace==${MEMPALACE_VERSION}"; \
       fi

EXPOSE 3000

CMD ["sh", "-c", "mkdir -p /root/.mempalace/palace && exec mcp-proxy --port 3000 -- python -m mempalace.mcp_server"]
