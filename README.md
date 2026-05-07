# 🛡️ RSC Cloud Native Workload Dashboard

Real-time monitoring dashboard for Rubrik Security Cloud (RSC) job events across all cloud native workloads.

> **Not affiliated with Rubrik.** This is an independent, community-built tool. See [Legal](#legal--disclaimer) for details.

---

## Overview

This tool connects to your RSC instance via the GraphQL API and provides a rolling 24-hour view of all cloud native protection job events across AWS, Azure, GCP, and M365. It features automatic incremental updates, interactive filtering, visual analytics, encrypted local caching, and data export.

**v1.0.1** introduces a full security hardening pass reviewed against OWASP Top 10, NIST SP 800-53, CIS Controls v8, and ISO 27001. See [Security](#security) for details.

---

## Features

| Feature | Details |
|---------|---------|
| 📊 **Rolling 24-hour view** | All cloud native job events, refreshed continuously |
| ⚡ **Auto-updating** | Incremental fetches every ~30 seconds |
| 🔍 **Interactive filtering** | By status, workload type, job type, cluster, or free-text search |
| 📈 **Visual analytics** | Status distribution, workload breakdown, hourly timeline charts |
| 🔴 **Failed jobs detail** | Expandable section with per-job error messages |
| 📥 **CSV / JSON export** | Download filtered data for reporting |
| 💾 **Encrypted disk cache** | Survives restarts; instant reload; AES-encrypted at rest |
| 🔐 **Optional password gate** | Set `DASHBOARD_PASSWORD` to require login |
| 🔑 **Token management** | Automatic refresh, retry on failure, rate-limit handling |
| 🔒 **Localhost binding** | Streamlit bound to `127.0.0.1` by default |

---

## Supported Workloads

| Cloud | Workloads |
|-------|-----------|
| **AWS** | EC2 Instances, EBS Volumes, RDS Instances, S3 Buckets, DynamoDB Tables, Accounts |
| **Azure** | VMs, Managed Disks, Subscriptions, SQL Databases, SQL Database Servers, Storage Accounts, DevOps Repositories |
| **GCP** | Compute Instances, Persistent Disks, Projects, Cloud SQL Instances, AlloyDB Clusters |
| **Other** | Exocompute, M365 Backup Storage |

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| Python | 3.9 or higher (3.12 recommended) |
| Network | HTTPS access to your RSC instance (port 443) |
| RSC Permissions | Service account with **ViewActivity** and **ViewInventory** roles |
| Disk Space | ~100 MB |
| RAM | 512 MB minimum |

> You must have a valid API key and an active Rubrik Security Cloud subscription. This tool does not bypass licensing or provide unauthorised access to any Rubrik features.

---

## Quick Start

### macOS / Linux

```bash
# Clone or download the repo
git clone https://github.com/jacobbryce1/rsc-events-dashboard.git
cd rsc-events-dashboard

# Install (macOS)
bash install/install_macos.sh

# Install (Linux)
bash install/install_linux.sh

# Configure credentials
./configure.sh        # interactive, or edit .env manually (see Configuration below)

# Run
./run.sh
```

### Windows (PowerShell)

```powershell
git clone https://github.com/jacobbryce1/rsc-events-dashboard.git
cd rsc-events-dashboard
.\install\install_windows.ps1
.\configure.bat       # or edit .env manually
.\run.bat
```

Dashboard opens at **http://localhost:8501** once running.

---

## Configuration

### 1. Create your `.env` file

Copy the example and fill in your RSC service account credentials:

```bash
cp .env.example .env
```

```dotenv
# .env
RSC_SERVICE_ACCOUNT_ID=client|xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
RSC_SERVICE_ACCOUNT_SECRET=your-secret-here
RSC_BASE_URL=https://your-org.my.rubrik.com
```

Or run the interactive configurator:

```bash
./configure.sh
```

> ⚠️ **Never commit `.env` to version control.** It is already listed in `.gitignore`.
> `RSC_BASE_URL` must match `https://*.my.rubrik.com` — the app validates this at startup
> and will refuse to run if the URL does not match.

### 2. RSC Service Account Setup

1. Log into RSC → **Settings** → **Service Accounts**
2. Create a new service account
3. Assign roles: **ViewActivity** and **ViewInventory** *(principle of least privilege)*
4. Copy the Client ID and Secret into your `.env` file

### 3. Optional: Password Protection

If the dashboard runs on a shared machine or is exposed beyond localhost, set a password:

```dotenv
# .env
DASHBOARD_PASSWORD=your-strong-password-here
```

When set, users see a login screen before any RSC data is displayed. Leave `DASHBOARD_PASSWORD` unset for trusted localhost-only use.

### 4. Optional: Log Level

```dotenv
# .env
LOG_LEVEL=WARNING    # Default. Change to INFO for verbose output, DEBUG for full traces.
```

---

## Usage

### Starting the Dashboard

```bash
cd ~/rsc-dashboard
./run.sh
```

### What to Expect

| Event | Duration |
|-------|----------|
| First launch (full 24 h scan) | 3–5 minutes |
| Subsequent visits (cache hit) | < 5 seconds |
| Incremental update | ~30 seconds |

### Dashboard Controls

| Control | Action |
|---------|--------|
| **🔄 Update** | Fetch new events since last update |
| **🔁 Full Reload** | Clear cache, rescan full 24 hours |
| **Auto-refresh toggle** | Enable/disable automatic periodic updates |
| **Interval slider** | Time between auto-refreshes (15 s – 5 min) |

### Filters

| Filter | Description |
|--------|-------------|
| Status | In Progress, Queued, Failed, Partial, Canceled, Completed |
| Workload Type | AWS EC2, Azure VM, GCP Compute, etc. |
| Job Type | Backup, Replication, Archive, Recovery, etc. |
| Cluster | RSC cluster name (shown when multiple clusters present) |
| Search | Free-text search on object name or ID |
| **Quick: Failed** | One-click — show only Failed / Partial |
| **Quick: Active** | One-click — show only In Progress / Queued |

---

## Security

v1.0.1 was reviewed against **OWASP Top 10 (2021)**, **NIST SP 800-53 Rev.5**, **CIS Controls v8**, and **ISO 27001:2022**. The following hardening measures are in place:

### Credential Protection
- Credentials are loaded from `.env` and wrapped in a `SecretStr` type — they never appear in `repr()`, log output, or exception tracebacks.
- `RSC_BASE_URL` is validated against an allowlist pattern (`https://*.my.rubrik.com`) at startup. Any other value raises an immediate error, preventing SSRF.
- The app validates all required credentials are present before any UI renders. Missing or placeholder values produce a clear error and halt startup.

### Encrypted Disk Cache
The local event cache is **AES-encrypted at rest** using [Fernet](https://cryptography.io/en/latest/fernet/) symmetric encryption (from the `cryptography` package).

- On first run, a random 256-bit key is generated and saved to `.cache.key` with `chmod 0o600` (owner read/write only).
- The cache data file (`.event_cache.bin`) is opaque ciphertext — unreadable without the key file.
- Both `.cache.key` and `.event_cache.bin` are excluded from version control via `.gitignore`.
- If the `cryptography` package is unavailable, disk persistence is disabled gracefully (in-memory only) rather than falling back to plaintext.

> 🔑 **Treat `.cache.key` like a password.** Back it up separately if you need cache persistence across reinstalls. Deleting it invalidates the cache file.

### Network Binding
Streamlit is bound to `127.0.0.1` (localhost only) via `.streamlit/config.toml`. The dashboard is not accessible to other hosts on the network by default.

If you need remote access, place an authenticated reverse proxy (nginx, Caddy, Traefik) in front of the Streamlit process. Do **not** change `address` to `0.0.0.0` without adding authentication.

### Dashboard Authentication
Set `DASHBOARD_PASSWORD` in your `.env` to enable a login screen. Password comparison uses `hmac.compare_digest` (constant-time) to prevent timing attacks.

### Error Handling
Raw exception messages, stack traces, and URL strings are never rendered in the browser UI. All errors are logged server-side; the UI shows only a sanitised message.

### Dependency Auditing
All dependencies are pinned to exact versions in `requirements.txt`. A GitHub Actions workflow (`security-audit.yml`) runs `pip-audit` on every push and weekly to detect known CVEs.

### Files Generated at Runtime

| File | Contents | Protected by |
|------|----------|--------------|
| `.env` | RSC credentials | `.gitignore`, file permissions |
| `.cache.key` | Fernet encryption key | `.gitignore`, `chmod 0o600` |
| `.event_cache.bin` | Encrypted RSC event data | `.gitignore`, Fernet encryption |

### Reporting Vulnerabilities
See [SECURITY.md](SECURITY.md) for our responsible disclosure process.

---

## Architecture

```
RSC GraphQL API (activitySeriesConnection)
         |
         | 20 filtered queries (4 parallel workers)
         v
+--------------------------------+
|   EventDataCollector           |
|   - Token lifecycle (SecretStr)|
|   - Retry + backoff            |
|   - Progress reporting         |
+---------------+----------------+
                |
                v
+--------------------------------+
|   IncrementalCache             |
|   - Rolling 24 h window        |
|   - Merge new / updated events |
|   - Expire old events          |
|   - AES-encrypted disk persist |
+---------------+----------------+
                |
                v
+--------------------------------+
|   Streamlit Dashboard          |
|   - Optional password gate     |
|   - KPIs and charts            |
|   - Filters and search         |
|   - Auto-refresh               |
|   - CSV / JSON export          |
+--------------------------------+
```

---

## Project Structure

```
rsc-dashboard/
├── dashboard.py            # Streamlit UI, auth gate, safe error handling
├── data_collector.py       # RSC API event fetching, parallel workers
├── rsc_client.py           # GraphQL client, token lifecycle (SecretStr)
├── incremental_cache.py    # Rolling 24 h cache, AES-encrypted disk persist
├── token_monitor.py        # Token health metrics
├── config.py               # SecretStr credentials, URL validation, startup check
├── utils.py                # DataFrame helpers
├── requirements.txt        # Pinned dependencies
├── .env                    # RSC credentials — NOT committed
├── .env.example            # Template
├── .cache.key              # Fernet key — NOT committed, chmod 0o600
├── .event_cache.bin        # Encrypted cache — NOT committed
├── .gitignore
├── .streamlit/
│   └── config.toml         # Localhost binding, telemetry off
├── .github/
│   └── workflows/
│       └── security-audit.yml  # pip-audit on push + weekly cron
├── assets/                 # Images
├── tests/                  # Validation test suite
├── docs/                   # Setup guide and troubleshooting
└── install/                # OS-specific install scripts
```

---

## Performance

| Operation | Duration |
|-----------|----------|
| Full 24 h load | 3–5 minutes |
| Incremental update | ~30 seconds |
| Dashboard restart (cache hit) | < 5 seconds |

The RSC API responds in ~30–40 seconds per request. The dashboard uses 4 parallel workers, which balances speed against server-side rate limits.

---

## Testing

Validate connectivity and data collection:

```bash
cd ~/rsc-dashboard
./test.sh
```

Run the dependency security audit locally:

```bash
pip install pip-audit
pip-audit -r requirements.txt
```

---

## Updating

```bash
cd ~/rsc-dashboard
source .venv/bin/activate
git pull                         # or copy new .py files over existing ones
pip install -r requirements.txt  # picks up any new/updated pinned deps
rm -f .event_cache.bin           # clear old cache after a major update
./run.sh
```

> If you are upgrading from v1.0.0: delete `.event_cache.json` (legacy plaintext cache) and let the new version create `.event_cache.bin` (encrypted) on first run.

---

## Uninstalling

```bash
rm -rf ~/rsc-dashboard
```

This removes all code, the virtual environment, credentials, cache, and the encryption key.

---

## Legal & Disclaimer

This project is an **independent, open-source tool** and is **not affiliated with, authorized, maintained, sponsored, or endorsed by Rubrik, Inc.** in any way. All product and company names are the registered trademarks of their respective owners. The use of any trade name or trademark is for identification and reference purposes only.

This software is provided **'as-is,' without warranty of any kind**. Use of this tool is at your own risk. The authors are not responsible for any data loss, API rate-limit overages, account suspensions, or security incidents resulting from the use of this software.

You must have a valid API key and an active subscription or license for Rubrik Security Cloud (RSC). This software does not bypass any licensing checks or provide unauthorised access to Rubrik features.

---

## License

[Apache 2.0](LICENSE)
