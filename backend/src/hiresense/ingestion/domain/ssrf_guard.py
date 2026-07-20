from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

_ALLOWED_SCHEMES = frozenset({"http", "https"})


def is_safe_probe_url(
    url: str,
    resolver: Callable[[str, int | None], list[Any]] = socket.getaddrinfo,
) -> bool:
    """True when ``url`` is safe for the server to fetch (SSRF guard).

    Rejects anything but http/https and any host that resolves to a
    non-globally-routable address: private (10/8, 172.16/12, 192.168/16),
    loopback (127/8, ::1), link-local — including the 169.254.169.254 cloud
    metadata endpoint — CGNAT (100.64/10), reserved, multicast, and the
    unspecified address. EVERY resolved A/AAAA record must be public; a single
    internal answer blocks the URL. Fails closed on parse or DNS errors.

    ``resolver`` matches ``socket.getaddrinfo`` and is injectable so callers can
    re-check each redirect hop and tests can exercise the logic offline.

    NOTE: DNS is resolved here and again by the HTTP client at connect time, so
    a rebinding attacker could still swap the answer in between. Pinning the
    validated address would need a custom transport; this check closes the
    common static-target SSRF and cloud-metadata-access cases.
    """
    parts = urlsplit(url)
    if parts.scheme not in _ALLOWED_SCHEMES:
        return False
    host = parts.hostname
    if not host:
        return False
    try:
        infos = resolver(host, parts.port)
    except (OSError, ValueError, UnicodeError):
        # gaierror (DNS failure) subclasses OSError; a malformed port raises
        # ValueError on parts.port. Any of these means "cannot verify" → block.
        return False
    addresses = [info[4][0] for info in infos if info and len(info) >= 5 and info[4]]
    if not addresses:
        return False
    return all(_is_globally_routable(addr) for addr in addresses)


def _is_globally_routable(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    # Unwrap IPv4-mapped IPv6 (e.g. ::ffff:169.254.169.254) so the embedded
    # private/link-local address is classified, not the v6 wrapper.
    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return bool(ip.is_global)
