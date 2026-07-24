from typing import Any, ClassVar

from pydantic_settings import DotEnvSettingsSource, EnvSettingsSource


class _CommaSeparatedMixin:
    """Mixin that splits comma-separated strings into lists for known fields."""

    _COMMA_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "enabled_job_sources",
            "supported_languages",
            "getonboard_categories",
            "job_closed_markers",
            "http_retry_status_codes",
            "cors_origins",
            "cors_allow_methods",
            "cors_allow_headers",
            "portfolio_sources",
            "themuse_categories",
            "adzuna_countries",
            "yc_jobs_roles",
            "dice_employment_types",
        }
    )

    def prepare_field_value(
        self, field_name: str, field: Any, value: Any, value_is_complex: bool
    ) -> Any:
        if field_name in self._COMMA_FIELDS and isinstance(value, str):
            return [s.strip() for s in value.split(",") if s.strip()]
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class _CommaSeparatedEnvSource(_CommaSeparatedMixin, EnvSettingsSource):
    pass


class _CommaSeparatedDotEnvSource(_CommaSeparatedMixin, DotEnvSettingsSource):
    pass
