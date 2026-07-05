from pydantic_settings import BaseSettings


class ObservabilitySettings(BaseSettings):
    """OpenTelemetry + logging configuration."""

    # --- Observability (OpenTelemetry) ---
    # Master switch. When False, setup_telemetry() is a no-op and the app
    # boots with plain default logging.
    otel_enabled: bool = True
    # service.name resource attribute (shows up as the service in Grafana).
    otel_service_name: str = "hiresense-backend"
    # OTLP collector endpoint. EMPTY → console/terminal exporter fallback
    # (traces/metrics/logs print to stdout, no collector needed). Set to
    # http://otel-lgtm:4317 (compose) or http://localhost:4317 (host) to ship
    # to the LGTM stack.
    otel_exporter_otlp_endpoint: str = ""
    # deployment.environment resource attribute.
    deployment_environment: str = "development"
    # Root log level for the central dictConfig.
    log_level: str = "INFO"
    # "json" for structured logs (prod/LGTM) or "console" for human-readable
    # lines (local dev).
    log_format: str = "json"
    # Parent-based trace sampling ratio in [0.0, 1.0]. 1.0 = sample everything.
    otel_traces_sampler_ratio: float = 1.0
    # Use an insecure (plaintext, no-TLS) OTLP gRPC connection. True is correct
    # for the local LGTM stack / docker-compose; set False to use TLS.
    otel_exporter_insecure: bool = True
