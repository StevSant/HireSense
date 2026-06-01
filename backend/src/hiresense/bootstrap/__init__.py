"""Composition layer: per-module builders that wire dependencies for create_app().

Each ``build_<module>`` constructs a bounded context's services + provider from
the shared infrastructure, returning the provider (and any service that a later
module depends on). Adding a module means adding one builder file here and one
call in ``hiresense.main.create_app`` — no edits to unrelated wiring.
"""
from hiresense.bootstrap.admin import AdminBuild, build_admin
from hiresense.bootstrap.analytics import AnalyticsBuild, build_analytics
from hiresense.bootstrap.applications import build_applications
from hiresense.bootstrap.autohunt import AutoHuntBuild, build_autohunt
from hiresense.bootstrap.cover_letter_templates import build_cover_letter_templates
from hiresense.bootstrap.identity import build_identity
from hiresense.bootstrap.ingestion import IngestionBuild, build_ingestion
from hiresense.bootstrap.interview import InterviewBuild, build_interview
from hiresense.bootstrap.matching import MatchingBuild, build_matching
from hiresense.bootstrap.optimization import OptimizationBuild, build_optimization
from hiresense.bootstrap.preference import PreferenceBuild, build_preference
from hiresense.bootstrap.profile import ProfileBuild, build_profile
from hiresense.bootstrap.research import build_research
from hiresense.bootstrap.shared_infra import SharedInfra, build_shared_infra
from hiresense.bootstrap.tracked_factory import make_tracked
from hiresense.bootstrap.tracking import TrackingBuild, build_tracking

__all__ = [
    "AdminBuild",
    "AnalyticsBuild",
    "AutoHuntBuild",
    "IngestionBuild",
    "InterviewBuild",
    "MatchingBuild",
    "OptimizationBuild",
    "PreferenceBuild",
    "ProfileBuild",
    "SharedInfra",
    "TrackingBuild",
    "build_admin",
    "build_analytics",
    "build_applications",
    "build_autohunt",
    "build_cover_letter_templates",
    "build_identity",
    "build_ingestion",
    "build_interview",
    "build_matching",
    "build_optimization",
    "build_preference",
    "build_profile",
    "build_research",
    "build_shared_infra",
    "build_tracking",
    "make_tracked",
]
