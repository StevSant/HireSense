"""Guard that infrastructure/registry.py imports every ORM table.

Alembic's ``--autogenerate`` only sees tables whose ORM classes have been
imported by the time ``Base.metadata`` is inspected, and the only module it
imports for that purpose is ``hiresense.infrastructure.registry``. If a new
``*Orm`` class is added but not wired into the registry, autogenerate silently
misses its table.

The check runs in a subprocess so import ordering is deterministic: the
registry is imported first (capturing exactly what it pulls in), then the whole
package is walked to discover the full set of ORM tables. Any table present in
the full set but absent from the registry-only set is a missing import.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

_PROBE = textwrap.dedent(
    """
    import importlib
    import json
    import pkgutil

    import hiresense
    from hiresense.infrastructure.database import Base

    # Importing the registry alone is what Alembic relies on.
    importlib.import_module("hiresense.infrastructure.registry")
    registry_tables = set(Base.metadata.tables)

    # Walk the whole package to discover every mapped table.
    for module in pkgutil.walk_packages(hiresense.__path__, hiresense.__name__ + "."):
        try:
            importlib.import_module(module.name)
        except Exception:
            # Some optional modules may fail to import in isolation; their ORM
            # classes, if any, would have been pulled in via the registry.
            pass
    all_tables = set(Base.metadata.tables)

    missing = sorted(all_tables - registry_tables)
    print(json.dumps(missing))
    """
)


def test_registry_imports_every_orm_table() -> None:
    result = subprocess.run(
        [sys.executable, "-c", _PROBE],
        capture_output=True,
        text=True,
        check=True,
    )
    import json

    missing = json.loads(result.stdout.strip().splitlines()[-1])
    assert missing == [], (
        "These ORM tables are not reachable through "
        "hiresense.infrastructure.registry and will be missed by Alembic "
        f"autogenerate: {missing}"
    )
