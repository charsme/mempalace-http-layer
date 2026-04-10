"""
Minimal OAuth 2.0 server for mempalace MCP access.

Supports:
  - Client Credentials flow  (claude.ai custom connector)
  - Basic Auth via verify    (Claude Code with credentials in URL)

Endpoints:
  GET  /.well-known/oauth-authorization-server  — discovery metadata
  POST /oauth/token                              — issue bearer token
  GET  /oauth/verify                             — ForwardAuth for Traefik
"""

import base64
import os
import secrets

from fastapi import FastAPI, Form, Request
from fastapi.responses import JSONResponse

app = FastAPI()

CLIENT_ID = os.environ["OAUTH_CLIENT_ID"]
CLIENT_SECRET = os.environ["OAUTH_CLIENT_SECRET"]
DOMAIN = os.environ["DOMAIN"]

# Optional static token — survives container restarts.
# If not set, tokens are ephemeral (invalidated on restart).
_STATIC_TOKEN = os.environ.get("OAUTH_STATIC_TOKEN", "")
_issued: set[str] = {_STATIC_TOKEN} if _STATIC_TOKEN else set()


@app.get("/.well-known/oauth-authorization-server")
async def metadata():
    return {
        "issuer": f"https://{DOMAIN}",
        "token_endpoint": f"https://{DOMAIN}/oauth/token",
        "grant_types_supported": ["client_credentials"],
        "token_endpoint_auth_methods_supported": ["client_secret_post"],
        "response_types_supported": ["token"],
    }


@app.post("/oauth/token")
async def token(
    grant_type: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...),
):
    if grant_type != "client_credentials":
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)
    if client_id != CLIENT_ID or client_secret != CLIENT_SECRET:
        return JSONResponse({"error": "invalid_client"}, status_code=401)

    access_token = _STATIC_TOKEN or secrets.token_urlsafe(32)
    _issued.add(access_token)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 86400 * 30,
    }


@app.get("/oauth/verify")
async def verify(request: Request):
    """Traefik ForwardAuth endpoint — validates Bearer or Basic credentials."""
    auth = request.headers.get("Authorization", "")

    # Bearer token (claude.ai after OAuth flow)
    if auth.startswith("Bearer "):
        if auth[7:] in _issued:
            return JSONResponse({"ok": True})

    # Basic Auth (Claude Code: credentials embedded in SSE URL)
    elif auth.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth[6:]).decode()
            user, pwd = decoded.split(":", 1)
            if user == CLIENT_ID and pwd == CLIENT_SECRET:
                return JSONResponse({"ok": True})
        except Exception:
            pass

    return JSONResponse(
        {"error": "unauthorized"},
        status_code=401,
        headers={"WWW-Authenticate": f'Bearer realm="mempalace"'},
    )
