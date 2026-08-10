from pydantic_settings import BaseSettings


class HttpSettings(BaseSettings):
    """Shared outbound HTTP client timeout + retry/backoff policy."""

    # HTTP
    http_timeout: float = 30.0
    # Retry/backoff for the shared outbound HTTP client (wraps every ingestion
    # source adapter). Transient transport errors (timeout, connection reset)
    # and the status codes below are retried with exponential backoff
    # (delay = http_retry_base_delay * 2**attempt), up to http_max_retries
    # extra attempts. 0 retries disables retrying.
    http_max_retries: int = 3
    http_retry_base_delay: float = 0.5
    http_retry_status_codes: list[int] = [429, 500, 502, 503, 504]
