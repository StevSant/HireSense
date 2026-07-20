from __future__ import annotations

import socket

from hiresense.ingestion.domain import is_safe_probe_url


def _resolver_for(*ips: str):
    """A getaddrinfo-shaped resolver returning the given IPs for any host."""

    def _resolve(host: str, port: int | None):
        return [
            (
                socket.AF_INET6 if ":" in ip else socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                (ip, port or 0),
            )
            for ip in ips
        ]

    return _resolve


def _raising_resolver(host: str, port: int | None):
    raise socket.gaierror("name resolution failed")


def test_public_ip_is_allowed() -> None:
    assert is_safe_probe_url("https://jobs.example.com/x", resolver=_resolver_for("93.184.216.34"))


def test_private_ip_is_blocked() -> None:
    assert not is_safe_probe_url("https://internal.example/x", resolver=_resolver_for("10.0.0.5"))


def test_loopback_is_blocked() -> None:
    assert not is_safe_probe_url("http://localhost/x", resolver=_resolver_for("127.0.0.1"))


def test_link_local_metadata_endpoint_is_blocked() -> None:
    # AWS/GCP/Azure cloud metadata service.
    assert not is_safe_probe_url(
        "http://169.254.169.254/latest/meta-data/",
        resolver=_resolver_for("169.254.169.254"),
    )


def test_cgnat_range_is_blocked() -> None:
    assert not is_safe_probe_url("https://x.example/x", resolver=_resolver_for("100.64.1.1"))


def test_any_private_answer_blocks_the_whole_url() -> None:
    # DNS returns one public and one private address → blocked (a rebinding /
    # multi-answer host must not slip through on its public record).
    resolver = _resolver_for("93.184.216.34", "10.0.0.1")
    assert not is_safe_probe_url("https://mixed.example/x", resolver=resolver)


def test_ipv4_mapped_private_is_blocked() -> None:
    assert not is_safe_probe_url("https://x.example/x", resolver=_resolver_for("::ffff:10.0.0.1"))


def test_non_http_scheme_is_blocked() -> None:
    assert not is_safe_probe_url("ftp://example.com/x", resolver=_resolver_for("93.184.216.34"))
    assert not is_safe_probe_url("file:///etc/passwd", resolver=_resolver_for("93.184.216.34"))


def test_missing_host_is_blocked() -> None:
    assert not is_safe_probe_url("http:///no-host", resolver=_resolver_for("93.184.216.34"))


def test_dns_failure_fails_closed() -> None:
    assert not is_safe_probe_url("https://nx.example/x", resolver=_raising_resolver)


def test_empty_resolution_fails_closed() -> None:
    assert not is_safe_probe_url("https://empty.example/x", resolver=lambda h, p: [])
