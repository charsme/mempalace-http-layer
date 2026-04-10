"""
Minimal OAuth 2.0 server for mempalace MCP access.

Supports:
  - Authorization Code + PKCE flow  (claude.ai MCP connector)
  - Client Credentials flow          (programmatic access)
  - Basic Auth via verify            (Claude Code with Bearer token)

Endpoints:
  GET  /.well-known/oauth-authorization-server  — discovery metadata
  GET  /authorize                               — auth code flow: login form
  POST /authorize                               — auth code flow: process login
  POST /oauth/token                             — issue bearer token (both grant types)
  GET  /oauth/verify                            — ForwardAuth for Traefik
"""

import base64
import hashlib
import os
import secrets

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

app = FastAPI()

CLIENT_ID = os.environ["OAUTH_CLIENT_ID"]
CLIENT_SECRET = os.environ["OAUTH_CLIENT_SECRET"]
DOMAIN = os.environ["DOMAIN"]

# Optional static token — survives container restarts.
_STATIC_TOKEN = os.environ.get("OAUTH_STATIC_TOKEN", "")
_issued: set[str] = {_STATIC_TOKEN} if _STATIC_TOKEN else set()

# In-memory stores for PKCE auth code flow
# { auth_code: { "code_challenge": str, "redirect_uri": str, "client_id": str } }
_auth_codes: dict[str, dict] = {}


@app.get("/.well-known/oauth-authorization-server")
async def metadata():
    return {
        "issuer": f"https://{DOMAIN}",
        "authorization_endpoint": f"https://{DOMAIN}/authorize",
        "token_endpoint": f"https://{DOMAIN}/oauth/token",
        "grant_types_supported": ["authorization_code", "client_credentials"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["client_secret_post", "none"],
        "response_types_supported": ["code"],
    }


@app.get("/authorize", response_class=HTMLResponse)
async def authorize_form(
    response_type: str = "",
    client_id: str = "",
    redirect_uri: str = "",
    code_challenge: str = "",
    code_challenge_method: str = "",
    state: str = "",
):
    if client_id != CLIENT_ID:
        return HTMLResponse("<h2>Unknown client</h2>", status_code=400)
    if response_type != "code":
        return HTMLResponse("<h2>Unsupported response_type</h2>", status_code=400)

    return HTMLResponse(f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MemPalace — Authorize</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: #0f0f0f; color: #e8e8e8; display: flex;
            justify-content: center; align-items: center; min-height: 100vh; }}
    .card {{ background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 12px;
             padding: 2rem; width: 100%; max-width: 360px; }}
    h1 {{ font-size: 1.2rem; margin-bottom: 0.25rem; }}
    p {{ font-size: 0.85rem; color: #888; margin-bottom: 1.5rem; }}
    label {{ font-size: 0.8rem; color: #aaa; display: block; margin-bottom: 0.25rem; }}
    input {{ width: 100%; padding: 0.6rem 0.75rem; border-radius: 6px;
             border: 1px solid #333; background: #111; color: #e8e8e8;
             font-size: 0.95rem; margin-bottom: 1rem; }}
    input:focus {{ outline: none; border-color: #555; }}
    button {{ width: 100%; padding: 0.7rem; border-radius: 6px; border: none;
              background: #e8e8e8; color: #0f0f0f; font-size: 0.95rem;
              font-weight: 600; cursor: pointer; }}
    button:hover {{ background: #fff; }}
    .error {{ color: #f87171; font-size: 0.85rem; margin-bottom: 1rem; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>MemPalace</h1>
    <p>Authorize access to your memory palace</p>
    <form method="post" action="/authorize">
      <input type="hidden" name="client_id" value="{client_id}">
      <input type="hidden" name="redirect_uri" value="{redirect_uri}">
      <input type="hidden" name="code_challenge" value="{code_challenge}">
      <input type="hidden" name="code_challenge_method" value="{code_challenge_method}">
      <input type="hidden" name="state" value="{state}">
      <label>Client Secret</label>
      <input type="password" name="client_secret" placeholder="Enter your client secret" autofocus>
      <button type="submit">Authorize</button>
    </form>
  </div>
</body>
</html>""")


@app.post("/authorize")
async def authorize_submit(
    client_id: str = Form(...),
    client_secret: str = Form(...),
    redirect_uri: str = Form(...),
    code_challenge: str = Form(...),
    code_challenge_method: str = Form("S256"),
    state: str = Form(""),
):
    if client_id != CLIENT_ID or client_secret != CLIENT_SECRET:
        return HTMLResponse(f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MemPalace — Authorize</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: #0f0f0f; color: #e8e8e8; display: flex;
            justify-content: center; align-items: center; min-height: 100vh; }}
    .card {{ background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 12px;
             padding: 2rem; width: 100%; max-width: 360px; }}
    h1 {{ font-size: 1.2rem; margin-bottom: 0.25rem; }}
    p {{ font-size: 0.85rem; color: #888; margin-bottom: 1.5rem; }}
    label {{ font-size: 0.8rem; color: #aaa; display: block; margin-bottom: 0.25rem; }}
    input {{ width: 100%; padding: 0.6rem 0.75rem; border-radius: 6px;
             border: 1px solid #333; background: #111; color: #e8e8e8;
             font-size: 0.95rem; margin-bottom: 1rem; }}
    input:focus {{ outline: none; border-color: #555; }}
    button {{ width: 100%; padding: 0.7rem; border-radius: 6px; border: none;
              background: #e8e8e8; color: #0f0f0f; font-size: 0.95rem;
              font-weight: 600; cursor: pointer; }}
    button:hover {{ background: #fff; }}
    .error {{ color: #f87171; font-size: 0.85rem; margin-bottom: 1rem; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>MemPalace</h1>
    <p>Authorize access to your memory palace</p>
    <form method="post" action="/authorize">
      <input type="hidden" name="client_id" value="{client_id}">
      <input type="hidden" name="redirect_uri" value="{redirect_uri}">
      <input type="hidden" name="code_challenge" value="{code_challenge}">
      <input type="hidden" name="code_challenge_method" value="{code_challenge_method}">
      <input type="hidden" name="state" value="{state}">
      <div class="error">Invalid client secret. Try again.</div>
      <label>Client Secret</label>
      <input type="password" name="client_secret" placeholder="Enter your client secret" autofocus>
      <button type="submit">Authorize</button>
    </form>
  </div>
</body>
</html>""", status_code=401)

    auth_code = secrets.token_urlsafe(32)
    _auth_codes[auth_code] = {
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
    }

    sep = "&" if "?" in redirect_uri else "?"
    location = f"{redirect_uri}{sep}code={auth_code}&state={state}"
    return RedirectResponse(location, status_code=302)


@app.post("/oauth/token")
async def token(
    grant_type: str = Form(...),
    # client_credentials fields
    client_id: str = Form(None),
    client_secret: str = Form(None),
    # authorization_code fields
    code: str = Form(None),
    code_verifier: str = Form(None),
    redirect_uri: str = Form(None),
):
    if grant_type == "client_credentials":
        if client_id != CLIENT_ID or client_secret != CLIENT_SECRET:
            return JSONResponse({"error": "invalid_client"}, status_code=401)
        access_token = _STATIC_TOKEN or secrets.token_urlsafe(32)
        _issued.add(access_token)
        return {"access_token": access_token, "token_type": "bearer", "expires_in": 86400 * 30}

    if grant_type == "authorization_code":
        stored = _auth_codes.pop(code, None)
        if not stored:
            return JSONResponse({"error": "invalid_grant"}, status_code=400)

        # PKCE verification: BASE64URL(SHA256(code_verifier)) must equal code_challenge
        digest = hashlib.sha256(code_verifier.encode()).digest()
        computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        if computed != stored["code_challenge"]:
            return JSONResponse({"error": "invalid_grant", "detail": "pkce_mismatch"}, status_code=400)

        if redirect_uri != stored["redirect_uri"]:
            return JSONResponse({"error": "invalid_grant", "detail": "redirect_uri_mismatch"}, status_code=400)

        access_token = _STATIC_TOKEN or secrets.token_urlsafe(32)
        _issued.add(access_token)
        return {"access_token": access_token, "token_type": "bearer", "expires_in": 86400 * 30}

    return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)


@app.get("/oauth/verify")
async def verify(request: Request):
    """Traefik ForwardAuth endpoint — validates Bearer or Basic credentials."""
    auth = request.headers.get("Authorization", "")

    if auth.startswith("Bearer "):
        if auth[7:] in _issued:
            return JSONResponse({"ok": True})

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
