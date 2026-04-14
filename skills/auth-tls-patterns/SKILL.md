---
name: auth-tls-patterns
description: >
  Use when your service needs authentication that works without friction
  locally but secures remote access, automatic TLS certificate setup, or
  token-based auth with auto-generation and localhost bypass.
---

# Authentication & TLS

## The Pattern

**Problem:** Your tool serves a web UI. Locally it should just work — no passwords, no login screens. Remotely it needs real authentication and HTTPS. You don't want to configure either manually.

**Approach:** Socket-level localhost bypass (unforgeable), cascading auth strategies with auto-generation, and a TLS setup cascade that picks the best available method automatically.

Pattern proven in production across multiple Python CLI tools and web services.

## Key Design Decisions

### 1. Localhost bypass — socket-level IP, not headers

The single most important auth decision: localhost connections skip all auth checks. But you MUST use the socket-level client IP, not HTTP headers:

```python
_LOCALHOST_ADDRS = {"127.0.0.1", "::1"}

async def dispatch(self, request: Request, call_next) -> Response:
    # client.host is the socket-level IP — cannot be forged by the client
    client_host = request.client.host if request.client else ""
    if client_host in _LOCALHOST_ADDRS:
        return await call_next(request)
```

This is unforgeable — unlike `X-Forwarded-For` or the `Host` header, `request.client.host` comes from the TCP connection's source address. A remote attacker cannot set it to `127.0.0.1`.

A simpler approach checks at the CLI level:

```python
auth_required = resolved_host != "127.0.0.1" and not no_auth
```

### 2. Auth cascade: PAM > password file > auto-generate

Resolve auth mode through a fallback chain:

```python
def _resolve_auth() -> tuple[str, str]:
    """Fallback chain for non-localhost:
      1. PAM available → ("pam", "")
      2. MY_TOOL_PASSWORD env → ("password", <env value>)
      3. ~/.config/my-tool/password file → ("password", <file value>)
      4. Auto-generate → ("password", <generated>)
    """
```

Auto-generation writes a random password to a file with restricted permissions:

```python
def generate_and_save_password() -> str:
    pw = secrets.token_urlsafe(20)
    path = get_password_path()
    _config_dir()  # ensures dir exists with mode 0700
    path.write_text(pw + "\n")
    path.chmod(0o600)
    return pw
```

### 3. Token-based auth with auto-generation

A simpler bearer token approach:

```python
def ensure_token() -> str:
    """Return the existing auth token or generate and persist a new one."""
    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text().strip()
        if token:
            return token
    token = secrets.token_urlsafe(32)
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(token + "\n")
    TOKEN_FILE.chmod(0o600)
    return token
```

The middleware checks Bearer tokens on protected paths:

```python
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if not request.app.state.auth_required:
            return await call_next(request)
        path = request.url.path
        if not _is_protected(path):
            return await call_next(request)
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            if token == request.app.state.auth_token:
                return await call_next(request)
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
```

### 4. TLS cascade: Tailscale > mkcert > self-signed

Implement a three-tier TLS cascade, trying the best option first:

```
Tailscale available + cert domains? → Real Let's Encrypt cert, auto-renewed
mkcert installed?                   → Locally-trusted cert, no browser warnings
Neither?                            → Self-signed via Python cryptography library
```

Self-signed generation is pure Python — no openssl binary needed:

```python
def generate_self_signed(cert_path, key_path, hostnames=None, days_valid=3650):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    # Build SAN with DNS names + loopback IPs
    san_entries = [x509.DNSName(h) for h in hostnames]
    san_entries.append(x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")))
    san_entries.append(x509.IPAddress(ipaddress.IPv6Address("::1")))
    # ... build and sign cert ...
    key_path.touch(mode=0o600, exist_ok=True)   # restrictive perms BEFORE write
    key_path.write_bytes(key_pem)
    key_path.chmod(0o600)
```

### 5. Constant-time comparison for secrets

Secrets and API tokens should use `hmac.compare_digest` to prevent timing attacks:

```python
if hmac.compare_digest(token, expected_key):
    return await call_next(request)
```

## Template / Starter Code

```python
# auth.py — localhost bypass + auto-generated token
import secrets
from pathlib import Path
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

TOKEN_PATH = Path.home() / ".config" / "my-tool" / "token"
_LOCALHOST = {"127.0.0.1", "::1"}
_PUBLIC_PATHS = frozenset({"/health", "/auth/status"})

def ensure_token() -> str:
    if TOKEN_PATH.exists():
        token = TOKEN_PATH.read_text().strip()
        if token:
            return token
    token = secrets.token_urlsafe(32)
    TOKEN_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    TOKEN_PATH.write_text(token + "\n")
    TOKEN_PATH.chmod(0o600)
    return token

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Localhost bypass — socket-level IP, unforgeable
        client_host = request.client.host if request.client else ""
        if client_host in _LOCALHOST:
            return await call_next(request)
        # Public paths
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)
        # Bearer token check
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer ") and auth[7:] == request.app.state.auth_token:
            return await call_next(request)
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
```

> **Note:** Without initializing `app.state.auth_token` and `app.state.auth_required`, the middleware will raise `AttributeError: 'State' object has no attribute 'auth_token'` on the first non-localhost request. Add to your FastAPI lifespan or startup:

```python
# In your FastAPI lifespan or startup:
app.state.auth_token = ensure_token()
app.state.auth_required = resolved_host != "127.0.0.1" and not no_auth
```

## Gotchas & Lessons Learned

1. **WebSocket connections bypass HTTP middleware.** FastAPI's `BaseHTTPMiddleware` is only invoked for HTTP requests, not WebSocket upgrades. Implement a separate `_ws_auth_check()` function that verifies session cookies and bearer tokens on WebSocket connections.

2. **Secrets read fresh from disk per request.** Reading secrets from disk on every request rather than caching at startup lets you rotate them without restarting the server. The alternative (caching at startup) means a rotated secret doesn't take effect until restart.

3. **Self-signed certs need SAN entries, not just CN.** Modern browsers require Subject Alternative Name entries. Include DNS names AND IP addresses in the SAN extension. Without SANs, Chrome rejects the cert even if the CN matches.

4. **Key file permissions: `touch(0o600)` then `write_bytes()` then `chmod(0o600)`.** The `touch` creates the file with restrictive permissions before any content is written. The final `chmod` ensures permissions survive regardless of umask. This belt-and-suspenders approach prevents the window where the key file exists with world-readable permissions.

5. **The redaction-wipe bug.** When `GET /api/settings` returns secret keys as `""` for security, a naive `PATCH` back to the server overwrites real keys with empty strings. The fix preserves existing keys by identifier match with a positional fallback. Any API that redacts secrets in GET responses must handle this in the PATCH/PUT path.
