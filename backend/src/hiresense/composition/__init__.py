"""Composition layer: per-module builders that wire dependencies for create_app().

Each ``build_<module>`` constructs a bounded context's services + provider from
the shared infrastructure, returning the provider (and any service that a later
module depends on). Adding a module means adding one builder file here and one
call in ``hiresense.main.create_app`` — no edits to unrelated wiring.
"""

from hiresense.composition.admin import AdminBuild, build_admin
from hiresense.composition.autopilot import AutopilotBuild, build_autopilot
from hiresense.composition.inbox import InboxBuild, build_inbox
from hiresense.composition.scheduler import SchedulerBuild, build_scheduler
from hiresense.composition.analytics import AnalyticsBuild, build_analytics
from hiresense.composition.applications import build_applications
from hiresense.composition.autohunt import AutoHuntBuild, build_autohunt
from hiresense.composition.cover_letter_templates import build_cover_letter_templates
from hiresense.composition.claims import ClaimsBuild, build_claims
from hiresense.composition.dimension_scorer_adapter import MatchingDimensionScorerAdapter
from hiresense.composition.identity import build_identity
from hiresense.composition.ingestion import IngestionBuild, build_ingestion
from hiresense.composition.interview import InterviewBuild, build_interview
from hiresense.composition.matching import MatchingBuild, build_matching
from hiresense.composition.network import NetworkBuild, build_network
from hiresense.composition.notifications import NotificationBuild, build_notifications
from hiresense.composition.opportunities import OpportunitiesBuild, build_opportunities
from hiresense.composition.optimization import OptimizationBuild, build_optimization
from hiresense.composition.outreach import OutreachBuild, build_outreach
from hiresense.composition.portfolio import PortfolioBuild, build_portfolio
from hiresense.composition.preference import PreferenceBuild, build_preference
from hiresense.composition.profile import ProfileBuild, build_profile
from hiresense.composition.research import build_research
from hiresense.composition.shared_infra import SharedInfra, build_shared_infra
from hiresense.composition.tracked_factory import make_tracked
from hiresense.composition.tracking import TrackingBuild, build_tracking

__all__ = [
    "AdminBuild",
    "AnalyticsBuild",
    "AutoHuntBuild",
    "ClaimsBuild",
    "AutopilotBuild",
    "InboxBuild",
    "IngestionBuild",
    "SchedulerBuild",
    "InterviewBuild",
    "MatchingDimensionScorerAdapter",
    "MatchingBuild",
    "NetworkBuild",
    "NotificationBuild",
    "OpportunitiesBuild",
    "OptimizationBuild",
    "OutreachBuild",
    "PortfolioBuild",
    "PreferenceBuild",
    "ProfileBuild",
    "SharedInfra",
    "TrackingBuild",
    "build_admin",
    "build_analytics",
    "build_autopilot",
    "build_inbox",
    "build_applications",
    "build_autohunt",
    "build_cover_letter_templates",
    "build_claims",
    "build_identity",
    "build_ingestion",
    "build_interview",
    "build_matching",
    "build_network",
    "build_notifications",
    "build_opportunities",
    "build_optimization",
    "build_outreach",
    "build_portfolio",
    "build_preference",
    "build_profile",
    "build_research",
    "build_scheduler",
    "build_shared_infra",
    "build_tracking",
    "make_tracked",
]
