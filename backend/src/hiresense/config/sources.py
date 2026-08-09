from typing import Any, get_args, get_origin

from pydantic_settings import DotEnvSettingsSource, EnvSettingsSource

# Element types a comma-separated string can be split into. Anything else
# (dicts, nested models) must be supplied as JSON, which is pydantic's own
# behaviour and is left untouched below.
_SPLITTABLE_ELEMENTS = frozenset({str, int, float})


def _is_splittable_list(field: Any) -> bool:
    """True when a field is a ``list`` of simple scalars.

    Derived from the annotation rather than a hand-maintained name allowlist:
    an allowlist silently drops any list field someone forgets to register, and
    the resulting failure is a raw pydantic JSON-parse error at startup with no
    hint that the field needed registering (this is how
    ``ENABLED_OPPORTUNITY_SOURCES`` shipped unparseable in ``.env.example``).
    """
    annotation = getattr(field, "annotation", None)
    if get_origin(annotation) is not list:
        return False
    args = get_args(annotation)
    return len(args) == 1 and args[0] in _SPLITTABLE_ELEMENTS


class _CommaSeparatedMixin:
    """Mixin that splits comma-separated strings into lists for scalar list fields."""

    def prepare_field_value(
        self, field_name: str, field: Any, value: Any, value_is_complex: bool
    ) -> Any:
        # A leading '[' means the operator wrote a JSON array; defer to pydantic
        # so both notations keep working.
        if (
            isinstance(value, str)
            and not value.lstrip().startswith("[")
            and _is_splittable_list(field)
        ):
            return [s.strip() for s in value.split(",") if s.strip()]
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class _CommaSeparatedEnvSource(_CommaSeparatedMixin, EnvSettingsSource):
    pass


class _CommaSeparatedDotEnvSource(_CommaSeparatedMixin, DotEnvSettingsSource):
    pass
