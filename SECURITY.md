# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x     | ✅ Yes    |

---

## Reporting a Vulnerability

**Please do NOT open a public GitHub issue for security vulnerabilities.**

This tool handles RSC service account credentials and displays a live, rolling view of your cloud native backup estate — including job status, object names, cluster topology, workload types, and error messages from failed protection jobs. Responsible disclosure is important.

### How to Report

Use **GitHub's private vulnerability reporting**:

1. Go to the [Security tab](../../security) of this repository
2. Click **"Report a vulnerability"**
3. Fill in the details — include steps to reproduce, impact assessment, and any suggested remediation if you have one

We aim to acknowledge reports within **3 business days** and provide a fix or mitigation within **14 days** for high/critical issues.

### What to Include

- A description of the vulnerability and its potential impact
- Steps to reproduce (proof-of-concept code if applicable)
- The version(s) affected
- Any suggested fix

### Out of Scope

- Vulnerabilities in Rubrik Security Cloud (RSC) itself — report those directly to Rubrik
- Denial-of-service against the local Streamlit process
- Issues that require physical access to the machine running the dashboard
- Rate-limit overages caused by aggressive refresh interval settings

---

## Security Design

### Credential Handling

- All credentials (`RSC_SERVICE_ACCOUNT_ID`, `RSC_SERVICE_ACCOUNT_SECRET`, `RSC_BASE_URL`) are loaded exclusively from environment variables or a `.env` file — never hardcoded in source.
- Credentials are immediately wrapped in a `SecretStr` type on load. `SecretStr` values never appear in `repr()`, `str()`, log output, or exception tracebacks — they render as `**********` in any context that would otherwise expose them.
- `RSC_BASE_URL` is validated against a strict allowlist pattern (`https://*.my.rubrik.com`) at startup. Any value that does not match raises an immediate error and halts the application before any UI renders, preventing Server-Side Request Forgery (SSRF).
- The app validates that all required credentials are present and non-placeholder before the Streamlit UI is shown to the user. An incomplete configuration produces a clear error screen, not a partially initialised dashboard.
- The `.env` file is listed in `.gitignore` and must never be committed to version control.

### Token Lifecycle

- Token acquisition and refresh are handled in `rsc_client.py`. The active token is stored as a `SecretStr` and never logged or surfaced in the UI.
- Tokens are proactively refreshed before expiry. On receipt of a 401 or 403 response, the token is force-refreshed and the request retried.
- Token health metrics are tracked in `token_monitor.py` — refresh counts and TTL metadata are available for diagnostics without exposing the token value itself.
- SSL errors during authentication are never retried — they raise immediately with a clear message, preventing silent MITM exposure.

### Network Security

- TLS certificate verification is explicitly enforced on every API call in `rsc_client.py`. There is no `verify=False` path.
- `SSLError` is caught and raised as a fatal error — it is never absorbed by the generic retry loop and never silently bypassed.
- All RSC API communication is HTTPS only. There is no HTTP fallback.
- The RSC GraphQL endpoint is derived from the validated `RSC_BASE_URL` — it cannot be redirected by environment variable injection due to the allowlist check at startup.

### Network Binding

- Streamlit is bound to `127.0.0.1` (localhost only) via `.streamlit/config.toml`. The dashboard is not accessible to other hosts on the network by default.
- Telemetry is disabled in `.streamlit/config.toml` — no usage data is sent to Streamlit's servers.
- If remote access is required, place an authenticated reverse proxy (nginx, Caddy, Traefik) in front of the Streamlit process. Do **not** change `server.address` to `0.0.0.0` without adding authentication at the proxy layer.

### Dashboard Authentication

- When `DASHBOARD_PASSWORD` is set in `.env`, a login screen is presented before any RSC data is rendered in the UI.
- Password comparison uses `hmac.compare_digest` (constant-time comparison) to prevent timing-based attacks that could reveal whether a guess was close to correct.
- Session state is managed by Streamlit's built-in session mechanism — authentication is per-session and does not persist across browser restarts.
- `DASHBOARD_PASSWORD` is loaded as a `SecretStr` and never appears in logs or tracebacks.

> The built-in password gate is suitable for trusted localhost or small-team use. For production deployments or shared infrastructure, use a reverse proxy with a hardened authentication layer (OAuth2, SSO, mTLS) instead of or in addition to the built-in gate.

### Encrypted Disk Cache

The local event cache is **AES-encrypted at rest** using [Fernet](https://cryptography.io/en/latest/fernet/) symmetric encryption from the `cryptography` package.

- On first run, a cryptographically random 256-bit key is generated using `os.urandom()` and saved to `.cache.key` with `chmod 0o600` (owner read/write only) before any data is written.
- The cache data file (`.event_cache.bin`) is opaque ciphertext — unreadable without the corresponding `.cache.key` file.
- Fernet provides authenticated encryption — any tampering with `.event_cache.bin` is detected and the cache is rejected on load rather than silently consuming corrupted data.
- Both `.cache.key` and `.event_cache.bin` are listed in `.gitignore` and must never be committed to version control.
- If the `cryptography` package is unavailable at runtime, disk persistence is disabled gracefully. The dashboard falls back to in-memory caching for the session rather than writing a plaintext fallback cache.

> **Treat `.cache.key` like a password.** Back it up separately if you need cache persistence across reinstalls. Deleting it permanently invalidates the existing cache file — a full 24-hour rescan will be triggered on next launch.

### Error Handling and Information Leakage

- Raw exception messages, stack traces, and URL strings are never rendered in the browser UI. All errors are caught in `dashboard.py`, logged server-side, and the UI displays only a sanitised, user-facing message.
- Failed job error messages fetched from the RSC API are displayed in the dashboard's failed jobs detail section. These are treated as untrusted strings — they are rendered as plain text, not HTML, preventing injection via RSC job error content.
- API response bodies are never logged in full. Only structured fields (status codes, message strings bounded in length) are recorded.

### Dependency Management

- All dependencies are pinned to exact versions in `requirements.txt`, preventing silent supply-chain upgrades to vulnerable versions.
- A GitHub Actions workflow (`.github/workflows/security-audit.yml`) runs `pip-audit` automatically on every push and on a weekly schedule to detect known CVEs in pinned dependencies.
- Run a local audit at any time with:

```bash
pip install pip-audit
pip-audit -r requirements.txt
```

---

## Files Generated at Runtime

| File | Contents | Protected by |
|------|----------|--------------|
| `.env` | RSC credentials and optional password | `.gitignore`, OS file permissions |
| `.cache.key` | Fernet AES encryption key | `.gitignore`, `chmod 0o600` |
| `.event_cache.bin` | AES-encrypted RSC event data | `.gitignore`, Fernet authenticated encryption |

> The `.cache.key` file is as sensitive as the credentials in `.env`. Access to `.cache.key` combined with `.event_cache.bin` grants full read access to the cached RSC event data. Both files must be protected with OS-level permissions and must not be stored on shared or world-readable filesystems.

---

## Threat Model

This tool is designed for **single-user or small-team use on a trusted host** — a security analyst or administrator running the dashboard on a local workstation or a dedicated bastion host. The threat model assumes:

- **The host is trusted.** The tool does not defend against a compromised OS or a malicious local user with filesystem access to `.cache.key` or `.event_cache.bin`. OS-level user separation and filesystem permissions are the primary controls for cache data at rest.
- **The RSC instance is trusted.** The tool validates `RSC_BASE_URL` at startup but does not defend against a compromised RSC instance returning malicious data. Failed job error messages from RSC are rendered as plain text (not HTML) in the dashboard — the most practical injection vector is mitigated — but downstream consumers of CSV/JSON exports should treat all field values as untrusted data.
- **The browser session is local.** The built-in password gate and Streamlit's session state are not designed for internet-facing multi-user deployments. If the dashboard is exposed beyond localhost, a hardened reverse proxy with proper authentication must be placed in front of it.
- **Network path to RSC is trusted.** TLS verification is enforced, but the tool does not implement certificate pinning. A compromised CA in the system trust store could perform MITM undetected.
- **The `.env` file is protected by the OS.** `SecretStr` wrapping and `.gitignore` are code-level controls — they do not replace OS file permissions. Do not store `.env` on shared or world-readable filesystems.

---

## Security Contact

For questions about the security design of this tool, open a GitHub Discussion rather than a private report.