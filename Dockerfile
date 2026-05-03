FROM python:3.12-slim

ARG MEMPALACE_VERSION=latest

# Install Node.js LTS (required for supergateway)
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Install supergateway (keeps stdio process alive across SSE connections)
# and mempalace at requested version
RUN npm install -g supergateway \
    && if [ "$MEMPALACE_VERSION" = "latest" ]; then \
         pip install --no-cache-dir mempalace; \
       else \
         pip install --no-cache-dir "mempalace==${MEMPALACE_VERSION}"; \
       fi

EXPOSE 3000

CMD ["supergateway", "--stdio", "python -m mempalace.mcp_server", "--port", "3000", "--host", "0.0.0.0"]
