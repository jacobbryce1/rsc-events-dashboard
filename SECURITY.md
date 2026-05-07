# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x     | ✅ Yes    |

## Reporting a Vulnerability

**Please do NOT open a public GitHub issue for security vulnerabilities.**

This tool handles RSC service account credentials and displays sensitive customer
backup estate data.  Responsible disclosure is important.

### How to Report

Use **GitHub's private vulnerability reporting**:

1. Go to the [Security tab](../../security) of this repository.
2. Click **"Report a vulnerability"**.
3. Fill in the details — include steps to reproduce, impact assessment, and
   any suggested remediation if you have one.

We aim to acknowledge reports within **3 business days** and provide a fix or
mitigation within **14 days** for high/critical issues.

### What to Include

- A description of the vulnerability and its potential impact
- Steps to reproduce (proof-of-concept code if applicable)
- The version(s) affected
- Any suggested fix

### Out of Scope

- Issues in Rubrik Security Cloud (RSC) itself — report those to Rubrik directly
- Denial-of-service against the local Streamlit process
- Issues that require physical access to the machine running the dashboard

## Security Design Notes

- **Credentials** are loaded from a `.env` file and never hardcoded.
- **Disk cache** is encrypted at rest (AES-128 via Fernet).  The key file
  (`.cache.key`) must be protected with OS-level permissions.
- **Dashboard** has no built-in multi-user authentication.  It is designed for
  localhost-only use.  If deployed on a shared or network-accessible host,
  add a reverse proxy with authentication.
- **Network** communication is HTTPS only; RSC_BASE_URL is validated at startup
  to prevent SSRF.

## Security Contact

For questions about the security design of this tool, open a GitHub Discussion
rather than a private report.
