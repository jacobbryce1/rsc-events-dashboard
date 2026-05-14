# RSC Cloud Native Workload Dashboard

Real-time monitoring dashboard for Rubrik Security Cloud (RSC) job events across all cloud native workloads.

> **Not affiliated with Rubrik.** This is an independent, community-built tool. See [Legal & Disclaimer](#legal--disclaimer) for full details.

---

## Overview

This tool connects to your RSC instance via the GraphQL API and provides a rolling 24-hour view of all cloud native protection job events across AWS, Azure, GCP, and M365. It features automatic incremental updates, interactive filtering, visual analytics, encrypted local caching, and data export.

**v1.0.1** includes a full security hardening pass reviewed against OWASP Top 10 (2021), NIST SP 800-53 Rev.5, CIS Controls v8, and ISO 27001:2022. See [Security](#security) for details.

---

## Features

| Feature | Details |
|---------|---------|
| 📊 Rolling 24-hour view | All cloud native job events, refreshed continuously |
| ⚡ Auto-updating | Incremental fetches every ~30 seconds |
| 🔍 Interactive filtering | By status, workload type, job type, cluster, or free-text search |
| 📈 Visual analytics | Status distribution, workload breakdown, hourly timeline charts |
| 🔴 Failed jobs detail | Expandable section with per-job error messages |
| 📥 CSV / JSON export | Download filtered data for reporting |
| 💾 Encrypted disk cache | Survives restarts; instant reload; AES-encrypted at rest |
| 🔐 Optional password gate | Set `DASHBOARD_PASSWORD` to require login |
| 🔑 Token management | Automatic refresh, retry on failure, rate-limit handling |
| 🔒 Localhost binding | Streamlit bound to `127.0.0.1` by default |

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
# Clone the repository
git clone https://github.com/jacobbryce1/rsc-events-dashboard.git
cd rsc-events-dashboard

# Create a virtual environment (either .venv or venv — both are detected automatically)
python3 -m venv .venv

# Configure credentials
./configure.sh        # interactive wizard, or edit .env manually (see Configuration)

# Run — dependencies are installed automatically on first launch
./run.sh
```

> **Note:** You no longer need to run `pip install -r requirements.txt` manually. `run.sh` installs all required packages (including `cryptography` for encrypted disk cache and `watchdog` for better Streamlit performance) automatically each time it launches. The install step is a no-op if packages are already up to date.

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

> ⚠️ **Never commit `.env` to version control.** It is already listed in `.gitignore`.
> `RSC_BASE_URL` must match `https://*.my.rubrik.com` — the app validates this at startup
> and will refuse to run if the URL does not match.

Or use the interactive configurator:

```bash
./configure.sh
```

### 2. RSC Service Account Setup

1. Log into RSC → **Settings** → **Service Accounts**
2. Create a new service account
3. Assign roles: **ViewActivity** and **ViewInventory** *(principle of least privilege)*
4. Copy the Client ID and Secret into your `.env` file

### 3. Tunable Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `RSC_BASE_URL` | *(required)* | Your RSC instance URL |
| `RSC_SERVICE_ACCOUNT_ID` | *(required)* | Service account client ID |
| `RSC_SERVICE_ACCOUNT_SECRET` | *(required)* | Service account secret |
| `DASHBOARD_PASSWORD` | *(unset)* | Enable login screen when set |
| `LOG_LEVEL` | `WARNING` | Set to `INFO` or `DEBUG` for verbose output |

### 4. Optional: Password Protection

If the dashboard runs on a shared machine or is exposed beyond localhost, set a password:

```dotenv
DASHBOARD_PASSWORD=your-strong-password-here
```

When set, users see a login screen before any RSC data is displayed. Leave unset for trusted localhost-only use.

### 5. Optional: Log Level

```dotenv
LOG_LEVEL=WARNING    # Default. INFO for verbose output, DEBUG for full traces.
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
| First launch (full 24-hour scan) | 3–5 minutes |
| Subsequent visits (cache hit) | < 5 seconds |
| Incremental update | ~30 seconds |

### Dashboard Controls

| Control | Action |
|---------|--------|
| **🔄 Update** | Fetch new events since last update |
| **🔁 Full Reload** | Clear cache, rescan full 24 hours |
| Auto-refresh toggle | Enable/disable automatic periodic updates |
| Interval slider | Time between auto-refreshes (15 s – 5 min) |

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

## Output Files

Each run generates the following files at runtime:

| File | Description |
|------|-------------|
| `.env` | RSC credentials — not committed, owner-read only |
| `.cache.key` | Fernet encryption key — not committed, `chmod 0o600` |
| `.event_cache.bin` | AES-encrypted RSC event cache — not committed |

Optional on-demand exports:

| File | Description |
|------|-------------|
| `export_TIMESTAMP.csv` | Filtered data export, sortable in Excel |
| `export_TIMESTAMP.json` | Filtered data export with metadata |

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
|   - Rolling 24-hour window     |
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
├── dashboard.py                    # Streamlit UI, auth gate, safe error handling
├── data_collector.py               # RSC API event fetching, parallel workers
├── rsc_client.py                   # GraphQL client, token lifecycle (SecretStr)
├── incremental_cache.py            # Rolling 24-hour cache, AES-encrypted persist
├── token_monitor.py                # Token health metrics
├── config.py                       # SecretStr credentials, URL validation
├── utils.py                        # DataFrame helpers
├── requirements.txt                # Pinned dependencies
├── .env                            # RSC credentials — NOT committed
├── .env.example                    # Template
├── .cache.key                      # Fernet key — NOT committed, chmod 0o600
├── .event_cache.bin                # Encrypted cache — NOT committed
├── .gitignore
├── .streamlit/
│   └── config.toml                 # Localhost binding, telemetry off
├── .github/
│   └── workflows/
│       └── security-audit.yml      # pip-audit on push + weekly cron
├── assets/                         # Images
├── tests/                          # Validation test suite
├── docs/                           # Setup guide and troubleshooting
└── install/                        # OS-specific install scripts
```

---

## Security

v1.0.1 was reviewed against **OWASP Top 10 (2021)**, **NIST SP 800-53 Rev.5**, **CIS Controls v8**, and **ISO 27001:2022**. The following hardening measures are in place:

### Credential Protection
- Credentials are loaded from `.env` and wrapped in a `SecretStr` type — they never appear in `repr()`, log output, or exception tracebacks.
- `RSC_BASE_URL` is validated against an allowlist pattern (`https://*.my.rubrik.com`) at startup. Any other value raises an immediate error, preventing SSRF.
- The app validates all required credentials are present before any UI renders. Missing or placeholder values produce a clear error and halt startup.

### Encrypted Disk Cache
The local event cache is **AES-encrypted at rest** using [Fernet](https://cryptography.io/en/latest/fernet/) symmetric encryption.

- On first run, a random 256-bit key is generated and saved to `.cache.key` with `chmod 0o600` (owner read/write only).
- The cache data file (`.event_cache.bin`) is opaque ciphertext — unreadable without the key file.
- Both `.cache.key` and `.event_cache.bin` are excluded from version control via `.gitignore`.
- If the `cryptography` package is unavailable, disk persistence is disabled gracefully (in-memory only) rather than falling back to plaintext.

> 🔑 **Treat `.cache.key` like a password.** Back it up separately if you need cache persistence across reinstalls. Deleting it invalidates the cache file.

### Network Binding
Streamlit is bound to `127.0.0.1` (localhost only) via `.streamlit/config.toml`. The dashboard is not accessible to other hosts on the network by default.

If you need remote access, place an authenticated reverse proxy (nginx, Caddy, Traefik) in front of the Streamlit process. Do **not** change `address` to `0.0.0.0` without adding authentication.

### Dashboard Authentication
Set `DASHBOARD_PASSWORD` in `.env` to enable a login screen. Password comparison uses `hmac.compare_digest` (constant-time) to prevent timing attacks.

### Error Handling
Raw exception messages, stack traces, and URL strings are never rendered in the browser UI. All errors are logged server-side; the UI shows only a sanitised message.

### Dependency Auditing
All dependencies are pinned to exact versions in `requirements.txt`. A GitHub Actions workflow (`security-audit.yml`) runs `pip-audit` on every push and weekly to detect known CVEs.

### Reporting Vulnerabilities
See [SECURITY.md](SECURITY.md) for the responsible disclosure process. Please do **not** open a public GitHub issue for security vulnerabilities.

---

## Performance

| Operation | Duration |
|-----------|----------|
| Full 24-hour load | 3–5 minutes |
| Incremental update | ~30 seconds |
| Dashboard restart (cache hit) | < 5 seconds |

The RSC API responds in ~30–40 seconds per request. The dashboard uses 4 parallel workers, balancing speed against server-side rate limits.

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
git pull
pip install -r requirements.txt    # picks up any new pinned deps
rm -f .event_cache.bin             # clear cache after a major update
./run.sh
```

> **Upgrading from v1.0.0?** Delete `.event_cache.json` (legacy plaintext cache). The new version creates `.event_cache.bin` (encrypted) on first run.

---

## Troubleshooting

**"RSC_BASE_URL is not valid"**
Your `.env` value must match `https://*.my.rubrik.com`. Check for trailing slashes or typos.

**"Authentication failed"**
Verify `RSC_SERVICE_ACCOUNT_ID` and `RSC_SERVICE_ACCOUNT_SECRET` in your `.env`. Confirm the service account is active in RSC Settings → Service Accounts.

**"Feature not licensed"**
Some workload types may not be enabled on your RSC instance. The dashboard skips unlicensed workloads automatically and reports which ones are unavailable.

**Timeouts on first load**
The initial 24-hour scan takes 3–5 minutes due to API response times. Subsequent visits use the encrypted cache and load in under 5 seconds.

**Rate limiting (429 responses)**
The tool respects `Retry-After` headers automatically. If you see frequent 429s, reduce the auto-refresh interval in the dashboard controls.

---

## Uninstalling

```bash
rm -rf ~/rsc-dashboard
```

This removes all code, the virtual environment, credentials, cache, and the encryption key.

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -am 'Add feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

Please run `pip-audit -r requirements.txt` before submitting and include test coverage for any new functionality.

---

## Legal & Disclaimer

This project is an **independent, open-source tool** and is **not affiliated with, authorized, maintained, sponsored, or endorsed by Rubrik, Inc.** in any way. All product and company names are the registered trademarks of their respective owners. The use of any trade name or trademark is for identification and reference purposes only and does not imply any affiliation with or endorsement by the trademark holder.

This software is provided **"as-is," without warranty of any kind**, express or implied, including but not limited to warranties of merchantability, fitness for a particular purpose, and non-infringement. Use of this tool is entirely at your own risk. The authors and contributors are not responsible for any data loss, API rate-limit overages, account suspensions, security incidents, or other damages resulting from the use or misuse of this software.

You must have a valid API key and an active subscription or license for Rubrik Security Cloud (RSC). This software does not bypass any licensing checks or provide unauthorised access to Rubrik features.

For questions about the security design of this tool, open a GitHub Discussion. To report a vulnerability, follow the process in [SECURITY.md](SECURITY.md).

---

## License

[Apache 2.0](LICENSE)