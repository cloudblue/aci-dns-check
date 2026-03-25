# ACI DNS Health Check

CloudBlue Connect EaaS extension that continuously monitors DNS resolution and TCP connectivity in Azure Container Instances (ACI).

Built to detect intermittent DNS failures like:
```
socket.gaierror: [Errno -3] Temporary failure in name resolution
```

## How it works

A single **schedulable** (`DNS Health Check`) runs at a configurable interval and for each host:

1. Logs the container's `/etc/resolv.conf` (DNS server configuration)
2. Resolves the hostname via `socket.getaddrinfo` (same code path as urllib3/requests)
3. Attempts a TCP connect to port 443 to verify reachability beyond DNS
4. Logs timing and results with clear `OK` / `WARN` / `FAIL` prefixes
5. Returns `success` if all pass, `fail` with details if any host fails

## Default hosts checked

| Host | Why |
|------|-----|
| `api.partnercenter.microsoft.com` | Microsoft Partner Center API |
| `login.microsoftonline.com` | Azure AD / Entra ID |
| `graph.microsoft.com` | Microsoft Graph API |
| `management.azure.com` | Azure Resource Manager |
| `portal.azure.com` | Azure Portal |
| `google.com` | Non-Microsoft DNS sanity check |
| `cloudflare.com` | Non-Microsoft DNS sanity check |
| `dns.google` | Non-Microsoft DNS sanity check |

If the non-Microsoft hosts also fail, the problem is not Azure-specific.

## Configuration

### Extra hosts

Set the `DNS_CHECK_EXTRA_HOSTS` variable (comma-separated) via the Connect portal or as an OS environment variable:

```
srvc-7374-6941.ext.cloudblue.io,apix.ingrammicro.com
```

### Schedule interval

Configure in the Connect portal under the extension's schedulable settings. Recommended: **every 1 minute** for catching intermittent failures.

## Local development

1. Copy and fill in the env file:
   ```bash
   cp .dns_check_dev.env.example .dns_check_dev.env
   # Edit with your API_KEY, ENVIRONMENT_ID, SERVER_ADDRESS
   ```

2. Run:
   ```bash
   docker-compose up dns_check_dev
   ```

## Example log output

```
INFO  ============================================================
INFO  DNS Health Check | 2026-03-25 18:35:04 UTC | 8 hosts
INFO  ============================================================
INFO  --- /etc/resolv.conf ---
INFO    nameserver 127.0.0.11
INFO  --- end resolv.conf ---
INFO    OK   | api.partnercenter.microsoft.com | DNS 88ms -> ['51.103.5.205'] | TCP 41ms
INFO    OK   | login.microsoftonline.com | DNS 17ms -> ['20.190.147.0', ...] | TCP 42ms
INFO    OK   | graph.microsoft.com | DNS 18ms -> ['20.190.177.152', ...] | TCP 45ms
INFO    OK   | management.azure.com | DNS 44ms -> ['4.150.240.10'] | TCP 48ms
INFO    OK   | portal.azure.com | DNS 49ms -> ['150.171.84.24'] | TCP 45ms
INFO    OK   | google.com | DNS 14ms -> ['192.178.218.100', ...] | TCP 111ms
INFO    OK   | cloudflare.com | DNS 16ms -> ['104.16.132.229', ...] | TCP 23ms
INFO    OK   | dns.google | DNS 18ms -> ['8.8.4.4', '8.8.8.8'] | TCP 30ms
INFO  ============================================================
INFO  Result: 8/8 passed
INFO  ============================================================
```

When a failure occurs:
```
ERROR   FAIL | api.partnercenter.microsoft.com | DNS 5002ms -> [Errno -3] Temporary failure in name resolution
```
