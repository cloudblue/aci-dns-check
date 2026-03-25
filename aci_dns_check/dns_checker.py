import os
import socket
import time
from datetime import datetime, timezone


DEFAULT_HOSTS = [
    # Microsoft Partner Center - the host from the original DNS failure
    "api.partnercenter.microsoft.com",
    # Azure AD / Entra ID - used for OAuth token acquisition
    "login.microsoftonline.com",
    # Microsoft Graph API
    "graph.microsoft.com",
    # Azure Resource Manager
    "management.azure.com",
    # Azure portal (publicly resolvable Azure endpoint)
    "portal.azure.com",
    # Non-Microsoft sanity checks - if these also fail, it's not Azure-specific
    "google.com",
    "cloudflare.com",
    "dns.google",
]


def get_extra_hosts(config):
    """Get additional hosts from extension config and/or OS environment.

    Supports comma-separated lists from:
      - Extension variable DNS_CHECK_EXTRA_HOSTS (Connect portal)
      - OS environment variable DNS_CHECK_EXTRA_HOSTS (container config)
    Both are merged and deduplicated.
    """
    hosts = set()

    sources = [os.environ.get("DNS_CHECK_EXTRA_HOSTS", "")]
    try:
        sources.append(config.get("DNS_CHECK_EXTRA_HOSTS", "") or "")
    except Exception:
        pass

    for source in sources:
        if source:
            for h in source.split(","):
                h = h.strip()
                if h:
                    hosts.add(h)

    return sorted(hosts)


def resolve_host(host):
    """Resolve a hostname via getaddrinfo (same path as urllib3/requests).

    Returns (success, ips_or_error, elapsed_ms).
    """
    start = time.monotonic()
    try:
        results = socket.getaddrinfo(host, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
        elapsed_ms = (time.monotonic() - start) * 1000
        ips = sorted(set(r[4][0] for r in results))
        return True, ips, elapsed_ms
    except socket.gaierror as e:
        elapsed_ms = (time.monotonic() - start) * 1000
        return False, str(e), elapsed_ms


def tcp_connect(host, port=443, timeout=5):
    """Attempt a raw TCP connect to verify network reachability beyond DNS.

    Returns (success, error_or_none, elapsed_ms).
    """
    start = time.monotonic()
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        try:
            elapsed_ms = (time.monotonic() - start) * 1000
        finally:
            sock.close()
        return True, None, elapsed_ms
    except Exception as e:
        elapsed_ms = (time.monotonic() - start) * 1000
        return False, str(e), elapsed_ms


def log_system_dns_config(logger):
    """Log /etc/resolv.conf to capture which DNS servers the container uses."""
    try:
        with open("/etc/resolv.conf") as f:
            content = f.read().strip()
        logger.info("--- /etc/resolv.conf ---")
        for line in content.splitlines():
            logger.info(f"  {line}")
        logger.info("--- end resolv.conf ---")
    except Exception as e:
        logger.warning(f"Could not read /etc/resolv.conf: {e}")


def run_checks(logger, config):
    """Run DNS + TCP checks for all configured hosts.

    Returns list of (host, dns_error, tcp_error) for failed hosts.
    """
    extra_hosts = get_extra_hosts(config)
    all_hosts = DEFAULT_HOSTS + extra_hosts

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    logger.info(f"{'=' * 60}")
    logger.info(f"DNS Health Check | {now} | {len(all_hosts)} hosts")
    logger.info(f"{'=' * 60}")

    if extra_hosts:
        logger.info(f"Extra hosts from config: {', '.join(extra_hosts)}")

    log_system_dns_config(logger)

    failures = []

    for host in all_hosts:
        dns_ok, dns_result, dns_ms = resolve_host(host)

        if dns_ok:
            tcp_ok, tcp_err, tcp_ms = tcp_connect(host)
            if tcp_ok:
                logger.info(
                    f"  OK   | {host} | DNS {dns_ms:.0f}ms -> {dns_result} | TCP {tcp_ms:.0f}ms"
                )
            else:
                logger.warning(
                    f"  WARN | {host} | DNS OK {dns_ms:.0f}ms -> {dns_result} | TCP FAIL: {tcp_err}"
                )
                failures.append((host, None, tcp_err))
        else:
            logger.error(
                f"  FAIL | {host} | DNS {dns_ms:.0f}ms -> {dns_result}"
            )
            failures.append((host, dns_result, None))

    logger.info(f"{'=' * 60}")

    passed = len(all_hosts) - len(failures)
    dns_failures = [h for h, de, te in failures if de]
    tcp_failures = [h for h, de, te in failures if te and not de]

    logger.info(f"Result: {passed}/{len(all_hosts)} passed")
    if dns_failures:
        logger.error(f"DNS failures: {', '.join(dns_failures)}")
    if tcp_failures:
        logger.warning(f"TCP-only failures (DNS OK): {', '.join(tcp_failures)}")
    logger.info(f"{'=' * 60}")

    return failures
