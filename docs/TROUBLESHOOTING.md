# RSC Cloud Native Workload Dashboard - Troubleshooting Guide

## Quick Diagnostics

Run the built-in test suite to identify the problem:

    cd ~/rsc-dashboard
    ./test.sh

---

## Common Issues

### 1. No module named requests or similar

Cause: Virtual environment not activated or packages not installed.

Fix:

    cd ~/rsc-dashboard
    source .venv/bin/activate
    pip install -r requirements.txt

---

### 2. Cannot reach RSC or Connection timeout

Cause: VPN not connected, DNS failure, or firewall blocking.

Check connectivity:

    curl -s https://your-org.my.rubrik.com -o /dev/null -w "%{http_code}"

Should return 401 or 405 (reachable). If 000 then check VPN, DNS, and firewall.

Fix:
- Connect to VPN if required
- Check DNS: nslookup your-org.my.rubrik.com
- Verify firewall allows HTTPS port 443

---

### 3. SSL Certificate Errors

Cause: Corporate proxy intercepting HTTPS or outdated SSL library.

Fix Option A - Corporate CA bundle:

    export REQUESTS_CA_BUNDLE=/path/to/corporate-ca-bundle.crt

Fix Option B - Update certifi:

    pip install --upgrade certifi
    export SSL_CERT_FILE=$(python -c "import certifi; print(certifi.where())")

---

### 4. 401 Unauthorized on all requests

Cause: Service account credentials incorrect, expired, or revoked.

Fix:
1. Verify .env has correct values with no extra spaces or quotes
2. Check service account is active in RSC Settings
3. Regenerate the secret if needed
4. Ensure URL has no trailing slash

---

### 5. Port 8501 already in use

Cause: Previous dashboard instance still running.

Fix macOS/Linux:

    kill -9 $(lsof -t -i :8501)

Or use different port:

    streamlit run dashboard.py --server.port 8502

Fix Windows:

    netstat -ano | findstr :8501
    taskkill /PID <pid> /F

---

### 6. Dashboard loads but shows 0 events

Cause: No cloud native jobs ran in last 24 hours or cache is stale.

Fix:
1. Delete cache: rm .event_cache.json
2. Click Full Reload in sidebar
3. Wait 3-5 minutes for full scan
4. Check RSC web UI for recent activity
5. Verify ViewActivity permission

---

### 7. LibreSSL Warning on macOS

Message: urllib3 v2 only supports OpenSSL 1.1.1+

Cause: Using Apple system Python with old SSL.

Fix:

    brew install python@3.12
    rm -rf .venv
    /opt/homebrew/bin/python3.12 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

---

### 8. Slow initial load (more than 5 minutes)

Cause: Normal. RSC API responds in 30s per request.

Expected: 20 types / 4 parallel = 5 waves x 35s = about 3 minutes. Larger environments take longer. Not fixable - RSC server limitation.

---

### 9. Token refresh failed

Cause: Temporary network interruption.

Behavior: Retries automatically (3 attempts with backoff).

If persistent:
1. Check VPN/network stability
2. Verify RSC instance is online
3. Check service account not revoked
4. Check for proxy issues

---

### 10. Windows Execution policy error

Fix:

    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

Or for current session only:

    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

---

### 11. Still 401 after token refresh

Cause: Race condition during network blip.

Usually resolves on next retry. If persistent: restart dashboard, check RSC health, verify credentials.

---

### 12. Events show Unknown status

Cause: RSC returned unmapped status value.

Fix: Add the status to STATUS_CATEGORIES in config.py.

---

### 13. Missing workload types

Cause: Type not in FILTERABLE_WORKLOAD_TYPES in config.py.

Fix: Run discovery script to find new filterable types and add to config.

---

### 14. Cache file grows large

Fix:

    rm .event_cache.json

Dashboard will do fresh full load on next start.

---

## Diagnostic Commands

Check Python:

    python3 --version

Check packages:

    source .venv/bin/activate
    pip list | grep -E "streamlit|pandas|requests|plotly"

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

Check cache:

    python3 -c "
    import json
    with open('.event_cache.json') as f:
        data = json.load(f)
    print('Cached events:', len(data.get('events', {})))
    "

---

## Getting Help

1. Run ./test.sh and note which test fails
2. Check this guide for the specific error
3. Verify RSC instance via web UI
4. Check terminal output for detailed messages

---

## Disclaimer

This is not a Rubrik built or maintained solution and carries no support or warranties.

Built by Jacob Bryce - Advisory SE, Strategic Accounts
