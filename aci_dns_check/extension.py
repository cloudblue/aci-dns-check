from connect.eaas.core.decorators import schedulable, variables
from connect.eaas.core.extension import EventsApplicationBase
from connect.eaas.core.responses import ScheduledExecutionResponse

from aci_dns_check.dns_checker import run_checks


@variables([
    {
        "name": "DNS_CHECK_EXTRA_HOSTS",
        "initial_value": "",
    },
])
class AciDnsCheckExt(EventsApplicationBase):

    @schedulable(
        "DNS Health Check",
        "Checks DNS resolution and TCP connectivity for Azure and other critical "
        "hosts. Schedule every 1-5 minutes to continuously monitor for DNS failures "
        "in ACI. Configure extra hosts via the DNS_CHECK_EXTRA_HOSTS variable "
        "(comma-separated).",
    )
    def check_dns_health(self, request):
        self.logger.info("DNS health check triggered")

        failures = run_checks(self.logger, self.config)

        if not failures:
            return ScheduledExecutionResponse.done()

        dns_failures = [h for h, de, te in failures if de]
        tcp_failures = [h for h, de, te in failures if te and not de]

        parts = []
        if dns_failures:
            parts.append(f"DNS failed: {', '.join(dns_failures)}")
        if tcp_failures:
            parts.append(f"TCP failed: {', '.join(tcp_failures)}")

        msg = " | ".join(parts)
        self.logger.error(f"Health check FAILED: {msg}")
        return ScheduledExecutionResponse.fail(msg)
