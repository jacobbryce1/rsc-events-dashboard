# RSC Cloud Native Workload Dashboard - Troubleshooting Guide

## Quick Diagnostics

Run the built-in test suite to identify the problem:

    cd ~/rsc-dashboard
    ./test.sh

---

## Common Issues

### 1. App refuses to start with URL validation error

Message: RSC_BASE_URL must match https://*.my.rubrik.com

Cause: The v1.0.1 security hardening validates RSC_BASE_URL against an allowlist pattern to prevent SSRF attacks. [2]

Fix:
- Ensure your .env URL matches the format: https://your-org.my.rubrik.com
- No trailing slash, no port number, no path
- If you use a custom DNS alias or proxy, update ALLOWED_URL_PATTERN in config.py

---

### 2. App refuses to start with missing credentials error

Message: RSC_SERVICE_ACCOUNT_ID and RSC_SERVICE_ACCOUNT_SECRET must be set

Cause: v1.0.1 validates all credentials are present and non-placeholder before any UI renders. [1]

Fix:
- Run ./configure.sh to set up credentials
- Or manually create .env with valid values (not the placeholder text from .env.example)
- Ensure no extra spaces or quotes around values

---

### 3. Cache file unreadable after upgrade from v1.0.0

Cause: v1.0.1 uses encrypted cache (.event_cache.bin) instead of plaintext (.event_cache.json). [3]

Fix:

    rm -f .event_cache.json
    rm -f .event_cache.bin
    rm -f .cache.key

The app will regenerate the encryption key and create a new encrypted cache on next run.

---

### 4. Decryption error on cache load

Message: Error loading cache or similar decryption failure

Cause: The .cache.key file was deleted or corrupted, or the .event_cache.bin was modified externally.

Fix:

    rm -f .cache.key .event_cache.bin

The app regenerates both files on next startup. A full 24h rescan will occur.

---

### 5. No module named requests (or any package)

Cause: Virtual environment not activated or packages not installed.

Fix:

    cd ~/rsc-dashboard
    source .venv/bin/activate
    pip install -r requirements.txt

---

### 6. Cannot reach RSC or Connection timeout

Cause: VPN not connected, DNS failure, or firewall blocking.

Check connectivity:

    curl -s https://your-org.my.rubrik.com -o /dev/null -w "%{http_code}"

Should return 401 or 405 (reachable). If 000 then check VPN, DNS, and firewall.

Fix:
- Connect to VPN if required
- Check DNS: nslookup your-org.my.rubrik.com
- Verify firewall allows HTTPS port 443

---

### 7. SSL Certificate Errors

Cause: Corporate proxy intercepting HTTPS or outdated SSL library.

Fix Option A - Corporate CA bundle:

    export REQUESTS_CA_BUNDLE=/path/to/corporate-ca-bundle.crt

Fix Option B - Update certifi:

    pip install --upgrade certifi
    export SSL_CERT_FILE=$(python -c "import certifi; print(certifi.where())")

---

### 8. 401 Unauthorized on all requests

Cause: Service account credentials incorrect, expired, or revoked.

Fix:
1. Verify .env has correct values with no extra spaces or quotes
2. Check service account is active in RSC Settings
3. Regenerate the secret if needed
4. Ensure URL has no trailing slash
5. Verify URL passes the validation pattern [2]

---

### 9. Port 8501 already in use

Cause: Previous dashboard instance still running.

Fix macOS/Linux:

    kill -9 $(lsof -t -i :8501)

Or use different port:

    streamlit run dashboard.py --server.port 8502

Fix Windows:

    netstat -ano | findstr :8501
    taskkill /PID <pid> /F

---

### 10. Dashboard loads but shows 0 events

Cause: No cloud native jobs ran in last 24 hours or cache is stale.

Fix:
1. Delete cache: rm .event_cache.bin
2. Click Full Reload in sidebar
3. Wait 3-5 minutes for full scan
4. Check RSC web UI for recent activity
5. Verify ViewActivity permission

---

### 11. LibreSSL Warning on macOS

Message: urllib3 v2 only supports OpenSSL 1.1.1+

Cause: Using Apple system Python with old SSL. Note: v1.0.1 no longer suppresses this warning globally per security review finding F-001. [2]

Fix:

    brew install python@3.12
    rm -rf .venv
    /opt/homebrew/bin/python3.12 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

---

### 12. Slow initial load (more than 5 minutes)

Cause: Normal. RSC API responds in 30s per request.

Expected: 20 types / 4 parallel = 5 waves x 35s = about 3 minutes. Not fixable - RSC server limitation.

---

### 13. Token refresh failed

Cause: Temporary network interruption.

Behavior: Retries automatically (3 attempts with backoff).

If persistent:
1. Check VPN/network stability
2. Verify RSC instance is online
3. Check service account not revoked
4. Check for proxy issues

---

### 14. Still 401 after token refresh

Cause: Race condition during network blip (resolved in v1.0.1 with per-request token passing).

Usually resolves on next retry. If persistent: restart dashboard, check RSC health, verify credentials.

---

### 15. Events show Unknown status

Cause: RSC returned unmapped status value.

Fix: Note the raw status value from terminal logs and add it to STATUS_CATEGORIES in config.py.

---

### 16. Windows Execution policy error

Fix:

    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

Or for current session only:

    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

---

### 17. Password prompt appears unexpectedly

Cause: DASHBOARD_PASSWORD is set in your .env file. [3]

Fix:
- Enter the password you configured
- Or remove the DASHBOARD_PASSWORD line from .env to disable the gate

---

### 18. Permission denied on .cache.key or .event_cache.bin

Cause: File permissions too restrictive or wrong user.

Fix:

    chmod 600 .cache.key .event_cache.bin
    # Or if owned by wrong user:
    chown $(whoami) .cache.key .event_cache.bin

---

### 19. pip-audit reports vulnerabilities

Cause: A pinned dependency has a known CVE.

Fix:

    pip install pip-audit
    pip-audit -r requirements.txt

If vulnerabilities are found, update the specific package version in requirements.txt and re-test.

---

## Diagnostic Commands

Check Python:

    python3 --version

Check packages:

    source .venv/bin/activate
    pip list | grep -E "streamlit|pandas|requests|plotly|cryptography"

Test RSC manually:

    source .venv/bin/activate
    python3 -c "
    from rsc_client import RSCClient
    from token_monitor import MetricsStore, TokenMonitor
    c = RSCClient(max_connections=2, timeout=30,
                  monitor=TokenMonitor(metrics_store=MetricsStore()),
                  metrics=MetricsStore())
    r = c.execute_query('{ deploymentVersion }')
    print('Connected! Version:', r.get('deploymentVersion'))
    "

Check cache state:

    python3 -c "
    from incremental_cache import IncrementalCache
    cache = IncrementalCache(persist_path='.event_cache.bin')
    print(f'Events: {cache.event_count}')
    print(f'Needs full load: {cache.needs_full_load}')
    print(f'Metrics: {cache.metrics}')
    "

Check encryption status:

    ls -la .cache.key .event_cache.bin
    # Both should exist and have 600 permissions

---

## Security-Related Issues

### Credentials appearing in logs

This should not happen in v1.0.1 as credentials are wrapped in SecretStr. [3] If you see credentials in terminal output:
1. Check you are running the latest version
2. Check no custom logging configuration is overriding the protection

### Cache file accessible by other users

Fix:

    chmod 600 .event_cache.bin .cache.key .env

### Dashboard accessible from network

The dashboard should only bind to localhost. [1] If accessible from other machines:
1. Check run.sh uses --server.address localhost
2. If remote access is needed, deploy behind a reverse proxy with authentication [1]

---

## Getting Help

1. Run ./test.sh and note which test fails
2. Check this guide for the specific error
3. Verify RSC instance via web UI
4. Check terminal output for detailed log messages (errors are sanitised in the browser UI but full details appear in the terminal) [1]

---

## Disclaimer

This is not a Rubrik built or maintained solution and carries no support or warranties.

Built by Jacob Bryce - Advisory SE, Strategic Accounts
