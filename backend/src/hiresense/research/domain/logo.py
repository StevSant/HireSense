from __future__ import annotations

from urllib.parse import urlparse


def logo_url(website: str | None, service_url: str) -> str | None:
    """Build a logo URL from a company website domain and a templated service
    URL (containing `{domain}`). Returns None when either input is missing."""
    if not website or not service_url:
        return None
    candidate = website if "//" in website else f"//{website}"
    host = urlparse(candidate).netloc or website
    domain = host.split("@")[-1].split(":")[0].strip().lower()
    if domain.startswith("www."):
        domain = domain[4:]
    if not domain:
        return None
    return service_url.replace("{domain}", domain)
