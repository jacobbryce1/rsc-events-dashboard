# RSC Cloud Native Workload Dashboard - Setup Guide

## Table of Contents

1. Overview
2. Prerequisites
3. Installation
4. Configuration
5. RSC Service Account Setup
6. Running the Dashboard
7. Validation and Testing
8. Daily Usage
9. Dashboard Features
10. Security
11. Architecture
12. Performance Notes
13. Updating
14. Uninstalling

---

## Overview

The RSC Cloud Native Workload Dashboard provides real-time monitoring of job events across all cloud native workloads protected by Rubrik Security Cloud (RSC). It displays a rolling 24-hour view with automatic incremental updates, encrypted local caching, and interactive filtering.

Version 1.0.1 includes a full security hardening pass reviewed against OWASP Top 10 (2021), NIST SP 800-53 Rev.5, CIS Controls v8, and ISO 27001:2022. [2]

### Key Capabilities

- Real-time monitoring - rolling 24-hour window of all cloud native job events
- Automatic updates - incremental fetching every 30-60 seconds
- Multi-cloud coverage - AWS, Azure, GCP workloads in a single view
- Interactive filtering - by status, workload type, job type, cluster, or text search
- Visual analytics - status distribution, workload breakdown, timeline charts
- Data export - CSV and JSON download of filtered results
- Encrypted disk cache - event data encrypted at rest using AES-128 via Fernet [1]
- Credential protection - secrets wrapped in SecretStr, never exposed in logs or tracebacks [3]
- Optional password gate - protect dashboard access on shared machines [3]

### Supported Workloads

| Cloud Provider | Workloads |
|----------------|-----------|
| AWS | EC2 Instances, EBS Volumes, RDS Instances, S3 Buckets, DynamoDB Tables, AWS Accounts |
| Azure | VMs, Managed Disks, Subscriptions, SQL Databases, SQL Database Servers, Storage Accounts, DevOps Repositories |
| GCP | Compute Instances, Persistent Disks, Projects, Cloud SQL Instances, AlloyDB Clusters |
| Other | Exocompute, M365 Backup Storage |

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| Python | 3.9 or higher (3.12 recommended) |
| Network | HTTPS access to your RSC instance on port 443 |
| RSC Account | Service account with API access |
| Permissions | ViewActivity and ViewInventory roles in RSC |
| Disk Space | ~100 MB (Python packages + encrypted event cache) |
| RAM | 512 MB minimum, 1 GB recommended |
| OS | macOS 12+, Windows 10+, or Linux (Ubuntu 20.04+, RHEL 8+) |

You must have a valid API key and an active Rubrik Security Cloud subscription. This tool does not bypass licensing or provide unauthorised access to any Rubrik features. [3]

---

## Installation

### macOS (Automatic)

    git clone https://github.com/jacobbryce1/rsc-events-dashboard.git
    cd rsc-events-dashboard
    bash install/install_macos.sh

The installer will:

1. Check and install Homebrew (if not present)
2. Check and install Python 3.12 (if needed)
3. Create ~/rsc-dashboard directory
4. Set up an isolated Python virtual environment
5. Install all pinned dependencies
6. Create launcher scripts (run.sh, test.sh, configure.sh)

### macOS (Manual)

    brew install python@3.12
    mkdir -p ~/rsc-dashboard
    cd ~/rsc-dashboard
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt

### Linux (Automatic)

    git clone https://github.com/jacobbryce1/rsc-events-dashboard.git
    cd rsc-events-dashboard
    bash install/install_linux.sh

Supports Ubuntu, Debian, RHEL, CentOS, Rocky, Alma, Fedora, SUSE, and Arch.

### Linux (Manual - Ubuntu/Debian)

    sudo apt-get update
    sudo apt-get install -y python3 python3-venv python3-pip
    mkdir -p ~/rsc-dashboard && cd ~/rsc-dashboard
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

### Linux (Manual - RHEL/CentOS/Rocky)

    sudo dnf install -y python3 python3-pip
    mkdir -p ~/rsc-dashboard && cd ~/rsc-dashboard
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

### Windows (Automatic - PowerShell)

    git clone https://github.com/jacobbryce1/rsc-events-dashboard.git
    cd rsc-events-dashboard
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
    .\install\install_windows.ps1

### Windows (Manual)

1. Download Python 3.12 from https://python.org/downloads/ (check Add to PATH)
2. Open PowerShell:

Commands:

    mkdir ~\rsc-dashboard
    cd ~\rsc-dashboard
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt

---

## Configuration

### Interactive (Recommended)

macOS and Linux:

    cd ~/rsc-dashboard
    ./configure.sh

Windows:

    cd ~\rsc-dashboard
    .\configure.bat

You will be prompted for:

| Field | Example | Where to Find |
|-------|---------|---------------|
| RSC Base URL | https://your-org.my.rubrik.com | Browser URL when logged into RSC |
| Service Account ID | client followed by a UUID | RSC > Settings > Service Accounts |
| Service Account Secret | Long alphanumeric string | Shown once when account is created |

### Manual

Create a file named .env in the dashboard directory:

    RSC_SERVICE_ACCOUNT_ID=client|xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    RSC_SERVICE_ACCOUNT_SECRET=your-secret-value-here
    RSC_BASE_URL=https://your-org.my.rubrik.com

On macOS/Linux, protect the file:

    chmod 600 .env

### URL Validation

The RSC_BASE_URL is validated at startup against the pattern `https://*.my.rubrik.com`. Any URL that does not match this pattern will be rejected to prevent SSRF attacks. [2] [3]

If you use a custom DNS alias or proxy URL for RSC, you will need to update the ALLOWED_URL_PATTERN in config.py to include your domain.

### Optional: Password Protection

If the dashboard runs on a shared machine or is exposed beyond localhost, set a password in your .env file: [3]

    DASHBOARD_PASSWORD=your-strong-password-here

When set, users see a login screen before any RSC data is displayed. Leave DASHBOARD_PASSWORD unset for trusted localhost-only use. [1]

---

## RSC Service Account Setup

1. Log into RSC at https://your-org.my.rubrik.com
2. Navigate to Settings then Service Accounts
3. Click Create Service Account
4. Set Name to dashboard-readonly
5. Set Description to Read-only access for Cloud Native Workload Dashboard
6. Assign roles: ViewActivity and ViewInventory
7. Click Create
8. Immediately copy the Client ID and Secret (secret shown only once)

### Minimum Required Permissions

| Permission | Why Needed |
|-----------|------------|
| ViewActivity | Query activitySeriesConnection for job events |
| ViewInventory | Resolve object names, IDs, and types |

No write permissions are needed. The dashboard is read-only. [3]

---

## Running the Dashboard

### macOS and Linux

    cd ~/rsc-dashboard
    ./run.sh

### Windows

    cd %USERPROFILE%\rsc-dashboard
    run.bat

### What Happens on Launch

1. Startup validation checks credentials and URL format [1]
2. First launch: Full 24-hour scan (3-5 minutes depending on environment)
3. Browser opens to http://localhost:8501
4. Data encrypted and cached to disk - next restart loads instantly [1]
5. Subsequent refreshes: Incremental updates (about 30 seconds)

### Stopping

Press Ctrl+C in the terminal.

### Different Port

    source .venv/bin/activate
    streamlit run dashboard.py --server.port 8502

### Network Binding

By default, the dashboard binds to localhost only and is not accessible from other machines. [1] If you need remote access, deploy behind a reverse proxy with authentication. Do not change the binding to 0.0.0.0 without adding authentication first. [2]

---

## Validation and Testing

    cd ~/rsc-dashboard
    ./test.sh           # macOS/Linux
    .\test.bat          # Windows

### What the Tests Validate

| Test | What It Checks |
|------|----------------|
| Startup validation | Credentials present, URL format valid |
| Full collection | All 20 workload types queried successfully |
| Data quality | Events have names, IDs, timestamps |
| Status mapping | All RSC statuses mapped to display categories |
| Incremental fetch | Can fetch only recent changes |
| Cache persistence | Encrypted data survives dashboard restart |
| Expiration | Old events older than 24h are properly removed |

### Dependency Security Audit

Run the dependency security audit locally: [3]

    pip install pip-audit
    pip-audit -r requirements.txt

---

## Daily Usage

### Starting

    cd ~/rsc-dashboard && ./run.sh

If cache is fresh (less than 24 hours), loads instantly from encrypted disk cache. Otherwise performs full scan.

### Refreshing Data

| Method | How | Speed |
|--------|-----|-------|
| Click Update | Sidebar button | About 30 seconds |
| Auto-refresh | Sidebar toggle | Automatic at chosen interval |
| Full Reload | Sidebar button | 3-5 minutes |
| Delete cache | rm .event_cache.bin then restart | Forces full rescan |

### When to Full Reload

- After changing RSC configuration
- If data looks stale or incomplete
- After adding new workloads to RSC
- After upgrading the dashboard

---

## Dashboard Features

### Instance Banner

Dark bar at top showing connected RSC instance name and URL with green status indicator. [1]

### KPI Cards

| Card | Meaning |
|------|---------|
| Total | Total events matching current filters |
| In Progress | Jobs currently running |
| Queued | Jobs waiting to start |
| Failed | Jobs that failed |
| Partial | Jobs that partially succeeded |
| Canceled | Jobs that were canceled |
| Completed | Jobs that finished successfully |

### Charts

- Status Pie Chart - donut showing status distribution
- Workload Bar Chart - top 12 workload types by count
- Job Type Bar Chart - top 12 job types by count
- Timeline - hourly stacked bar over 24 hours

### Failed Jobs Section

Automatically shown when failed events exist with object name, type, job, start/end time, duration, and error message.

### Events Table

Sortable table: Status, Object Name, Object ID, Workload Type, Job Type, Start Time, End Time, Elapsed, Data Transferred, Logical Size, Progress, Throughput, Cluster.

### Filters

| Filter | Type | Description |
|--------|------|-------------|
| Status | Multi-select | Filter by status category |
| Workload Type | Multi-select | Filter by cloud workload |
| Job Type | Multi-select | Filter by activity type |
| Cluster | Multi-select | Filter by RSC cluster |
| Search | Text | Free-text on name or ID |
| Quick Failed | Button | Show only Failed and Partial |
| Quick Active | Button | Show only In Progress and Queued |
| Quick All | Button | Clear filters |

### Export

- CSV download of filtered table
- JSON download of all filtered data

### Footer

Shows version, build number, RSC instance, cache status, and encryption status. [1]

---

## Security

### Credential Protection

- Credentials loaded from .env and wrapped in SecretStr - never appear in repr(), logs, or tracebacks [3]
- RSC_BASE_URL validated against allowlist pattern at startup to prevent SSRF [2] [3]
- App validates all required credentials before any UI renders [1]

### Data at Rest

- Event cache encrypted using AES-128 via Fernet [1]
- Encryption key stored in .cache.key file with restrictive permissions
- Cache file is .event_cache.bin (binary encrypted format)
- Both .cache.key and .event_cache.bin must be in .gitignore [1]

### Access Control

- Dashboard binds to localhost only by default [1]
- Optional DASHBOARD_PASSWORD environment variable for shared environments [3]
- No built-in multi-user authentication - use reverse proxy for shared deployments [1]

### Error Handling

- Stack traces and raw exceptions never shown in the Streamlit UI [1]
- Errors logged internally with full detail for debugging
- Users see sanitised, friendly error messages

### Supply Chain

- All dependencies pinned to exact versions in requirements.txt [2]
- GitHub Actions workflow runs pip-audit on every push [3]

### Files to Protect

| File | Contains | Permissions |
|------|----------|-------------|
| .env | RSC credentials | chmod 600 |
| .cache.key | Encryption key | chmod 600 |
| .event_cache.bin | Encrypted event data | chmod 600 |

---

## Architecture

    RSC GraphQL API (activitySeriesConnection)
         |
         | 20 filtered queries (4 parallel)
         v
    EventDataCollector (token mgmt, retry, progress)
         |
         v
    IncrementalCache (24h window, encrypt, merge, expire, persist)
         |
         v
    Streamlit Dashboard (charts, filters, export, password gate)

### Key Files

| File | Purpose |
|------|---------|
| dashboard.py | Streamlit UI with security gates |
| data_collector.py | RSC API event fetching |
| rsc_client.py | GraphQL client with token management |
| incremental_cache.py | Encrypted rolling cache with persistence |
| token_monitor.py | Token health metrics |
| config.py | Configuration, validation, and mappings |
| utils.py | Helpers |
| SECURITY.md | Vulnerability disclosure process |

---

## Performance Notes

| Metric | Value |
|--------|-------|
| Response time per request | 30-40 seconds |
| Optimal parallelism | 4 workers |
| Token lifetime | 12 hours |
| Full load time | 3-5 minutes |
| Incremental update | About 30 seconds |
| Cached restart | Less than 5 seconds |

Tips: Keep auto-refresh at 60s or higher. Initial load is always slow due to RSC API. Encrypted disk cache enables instant restarts.

---

## Updating

    cd ~/rsc-dashboard
    source .venv/bin/activate
    git pull
    pip install -r requirements.txt
    rm -f .event_cache.bin
    ./run.sh

If upgrading from v1.0.0: delete .event_cache.json (legacy plaintext cache) and let the new version create .event_cache.bin (encrypted) on first run. [3]

Always use `pip install -r requirements.txt` to maintain pinned versions. Do not run `pip install --upgrade` on individual packages as this breaks the version lock.

Version shown in sidebar and footer. [1]

---

## Uninstalling

macOS/Linux:

    rm -rf ~/rsc-dashboard

Windows:

    Remove-Item -Recurse -Force ~\rsc-dashboard

---

## Disclaimer

This is not a Rubrik built or maintained solution and carries no support or warranties. [1]

Built by Jacob Bryce - Advisory SE, Strategic Accounts
