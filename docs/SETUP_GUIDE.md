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
10. Architecture
11. Performance Notes
12. Updating
13. Uninstalling

---

## Overview

The RSC Cloud Native Workload Dashboard provides real-time monitoring of job events across all cloud native workloads protected by Rubrik Security Cloud (RSC). It displays a rolling 24-hour view with automatic incremental updates.

### Key Capabilities

- Real-time monitoring - rolling 24-hour window of all cloud native job events
- Automatic updates - incremental fetching every 30-60 seconds
- Multi-cloud coverage - AWS, Azure, GCP workloads in a single view
- Interactive filtering - by status, workload type, job type, cluster, or text search
- Visual analytics - status distribution, workload breakdown, timeline charts
- Data export - CSV and JSON download of filtered results
- Resilient - disk-cached data survives restarts, automatic token management

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
| Disk Space | ~100 MB (Python packages + event cache) |
| RAM | 512 MB minimum, 1 GB recommended |
| OS | macOS 12+, Windows 10+, or Linux (Ubuntu 20.04+, RHEL 8+) |

---

## Installation

### macOS (Automatic)

Extract the package and run the installer:

    tar -xzf rsc-cloud-native-dashboard-1.0.0.tar.gz
    cd rsc-cloud-native-dashboard-1.0.0
    bash install/install_macos.sh

The installer will:

1. Check and install Homebrew (if not present)
2. Check and install Python 3.12 (if needed)
3. Create ~/rsc-dashboard directory
4. Set up an isolated Python virtual environment
5. Install all required packages
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

    tar -xzf rsc-cloud-native-dashboard-1.0.0.tar.gz
    cd rsc-cloud-native-dashboard-1.0.0
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

    Expand-Archive rsc-cloud-native-dashboard-1.0.0.zip -DestinationPath .
    cd rsc-cloud-native-dashboard-1.0.0
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

Create a file named .env in the dashboard directory with these contents:

    RSC_SERVICE_ACCOUNT_ID=client|xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    RSC_SERVICE_ACCOUNT_SECRET=your-secret-value-here
    RSC_BASE_URL=https://your-org.my.rubrik.com

On macOS/Linux, protect the file:

    chmod 600 .env

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

No write permissions are needed. The dashboard is read-only.

---

## Running the Dashboard

### macOS and Linux

    cd ~/rsc-dashboard
    ./run.sh

### Windows

    cd %USERPROFILE%\rsc-dashboard
    run.bat

### What Happens on Launch

1. First launch: Full 24-hour scan (3-5 minutes depending on environment)
2. Browser opens to http://localhost:8501
3. Data cached to disk - next restart loads instantly
4. Subsequent refreshes: Incremental updates (about 30 seconds)

### Stopping

Press Ctrl+C in the terminal.

### Different Port

    source .venv/bin/activate
    streamlit run dashboard.py --server.port 8502

---

## Validation and Testing

    cd ~/rsc-dashboard
    ./test.sh           # macOS/Linux
    .\test.bat          # Windows

### What the Tests Validate

| Test | What It Checks |
|------|----------------|
| Full collection | All 20 workload types queried successfully |
| Data quality | Events have names, IDs, timestamps |
| Status mapping | All RSC statuses mapped to display categories |
| Incremental fetch | Can fetch only recent changes |
| Cache persistence | Data survives dashboard restart |
| Expiration | Old events older than 24h are properly removed |

---

## Daily Usage

### Starting

    cd ~/rsc-dashboard && ./run.sh

If cache is fresh (less than 24 hours), loads instantly. Otherwise performs full scan.

### Refreshing Data

| Method | How | Speed |
|--------|-----|-------|
| Click Update | Sidebar button | About 30 seconds |
| Auto-refresh | Sidebar toggle | Automatic at chosen interval |
| Full Reload | Sidebar button | 3-5 minutes |
| Delete cache | rm .event_cache.json then restart | Forces full rescan |

### When to Full Reload

- After changing RSC configuration
- If data looks stale or incomplete
- After adding new workloads to RSC
- After upgrading the dashboard

---

## Dashboard Features

### Instance Banner

Dark bar at top showing connected RSC instance name and URL with green status indicator.

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

---

## Architecture

    RSC GraphQL API
         |
         | 20 filtered queries (4 parallel)
         v
    EventDataCollector (token mgmt, retry, progress)
         |
         v
    IncrementalCache (24h window, merge, expire, disk persist)
         |
         v
    Streamlit Dashboard (charts, filters, export)

### Key Files

| File | Purpose |
|------|---------|
| dashboard.py | Streamlit UI |
| data_collector.py | RSC API fetching |
| rsc_client.py | GraphQL client with token management |
| incremental_cache.py | Rolling cache with persistence |
| token_monitor.py | Token health metrics |
| config.py | Configuration and mappings |
| utils.py | Helpers |

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

Tips: Keep auto-refresh at 60s or higher. Initial load is always slow due to RSC API. Disk cache enables instant restarts.

---

## Updating

    cd ~/rsc-dashboard
    source .venv/bin/activate
    # Copy new .py files over existing
    pip install -r requirements.txt
    rm -f .event_cache.json
    ./run.sh

Version shown in sidebar and footer.

---

## Uninstalling

macOS/Linux:

    rm -rf ~/rsc-dashboard

Windows:

    Remove-Item -Recurse -Force ~\rsc-dashboard

---

## Disclaimer

This is not a Rubrik built or maintained solution and carries no support or warranties.

Built by Jacob Bryce - Advisory SE, Strategic Accounts
