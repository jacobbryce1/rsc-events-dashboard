# tests/test_01_connectivity.py
"""
Test 1: Can we reach the RSC instance at all?
Run this FIRST before anything else.
"""
import sys
import os
import requests
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv

load_dotenv()


def test_env_variables_exist():
    """Verify all required environment variables are set."""
    print("\n🔍 Checking environment variables...")

    required_vars = [
        "RSC_SERVICE_ACCOUNT_ID",
        "RSC_SERVICE_ACCOUNT_SECRET",
        "RSC_BASE_URL",
    ]

    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing.append(var)
            print(f"   ❌ {var}: NOT SET")
        else:
            # Mask secrets
            if "SECRET" in var:
                masked = value[:4] + "****" + value[-4:]
            elif "ID" in var:
                masked = value[:8] + "****"
            else:
                masked = value
            print(f"   ✅ {var}: {masked}")

    assert not missing, f"Missing environment variables: {missing}"


def test_base_url_format():
    """Verify the RSC URL is properly formatted."""
    print("\n🔍 Validating RSC URL format...")

    base_url = os.getenv("RSC_BASE_URL", "")
    parsed = urlparse(base_url)

    assert parsed.scheme == "https", f"URL must use HTTPS, got: {parsed.scheme}"
    assert parsed.netloc, "URL must have a hostname"
    assert "rubrik.com" in parsed.netloc or "rubrik" in parsed.netloc, \
        f"URL doesn't look like an RSC instance: {parsed.netloc}"
    assert not base_url.endswith("/"), "URL should not end with /"

    print(f"   ✅ URL format valid: {base_url}")


def test_network_reachability():
    """Test basic HTTPS connectivity to the RSC instance."""
    print("\n🔍 Testing network connectivity to RSC...")

    base_url = os.getenv("RSC_BASE_URL", "")

    try:
        # Just test TCP/TLS connectivity — expect 404 or 401, not connection error
        response = requests.get(
            f"{base_url}/api/graphql",
            timeout=10,
            allow_redirects=False,
        )
        print(f"   ✅ RSC reachable (HTTP {response.status_code})")
        # Any HTTP response means we reached the server
        assert response.status_code in [200, 401, 403, 404, 405, 302], \
            f"Unexpected status: {response.status_code}"

    except requests.exceptions.SSLError as e:
        print(f"   ❌ SSL Error: {e}")
        print("   💡 If behind corporate proxy, set REQUESTS_CA_BUNDLE")
        raise

    except requests.exceptions.ConnectionError as e:
        print(f"   ❌ Connection Error: {e}")
        print("   💡 Check VPN connection or DNS resolution")
        raise

    except requests.exceptions.Timeout:
        print("   ❌ Connection timed out after 10s")
        print("   💡 Check firewall rules or VPN")
        raise


def test_dns_resolution():
    """Verify DNS resolution for the RSC hostname."""
    print("\n🔍 Testing DNS resolution...")
    import socket

    base_url = os.getenv("RSC_BASE_URL", "")
    hostname = urlparse(base_url).netloc

    try:
        ip = socket.gethostbyname(hostname)
        print(f"   ✅ {hostname} resolves to {ip}")
    except socket.gaierror as e:
        print(f"   ❌ DNS resolution failed for {hostname}: {e}")
        raise


if __name__ == "__main__":
    tests = [
        test_env_variables_exist,
        test_base_url_format,
        test_dns_resolution,
        test_network_reachability,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"   ❌ FAILED: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Connectivity: {passed} passed, {failed} failed")
    if failed:
        print("⚠️  Fix connectivity issues before proceeding.")
        sys.exit(1)
    else:
        print("✅ All connectivity tests passed. Proceed to authentication tests.")