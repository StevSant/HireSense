from __future__ import annotations


def get_cv_optimizer():
    raise NotImplementedError(
        "Must be overridden during app startup via dependency_overrides"
    )
