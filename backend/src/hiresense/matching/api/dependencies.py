from __future__ import annotations


def get_matching_orchestrator():
    raise NotImplementedError("Must be overridden during app startup via dependency_overrides")


def get_batch_evaluation_service():
    raise NotImplementedError("Must be overridden during app startup via dependency_overrides")


def get_tracking_service_for_matching():
    raise NotImplementedError("Must be overridden during app startup via dependency_overrides")


def get_ingestion_orchestrator_for_matching():
    raise NotImplementedError("Must be overridden during app startup via dependency_overrides")
