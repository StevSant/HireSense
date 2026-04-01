from __future__ import annotations


def get_profile_service():
    raise NotImplementedError("Must be overridden during app startup via dependency_overrides")
