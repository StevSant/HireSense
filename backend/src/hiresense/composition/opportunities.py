from __future__ import annotations

from dataclasses import dataclass

from hiresense.composition.shared_infra import SharedInfra
from hiresense.opportunities.adapters import ConfsTechAdapter, CuratedImportAdapter
from hiresense.opportunities.api.provider import OpportunitiesProvider
from hiresense.opportunities.domain.confs_tech_normalizer import ConfsTechNormalizer
from hiresense.opportunities.domain.curated_import_normalizer import CuratedImportNormalizer
from hiresense.opportunities.domain.services import OpportunityIngestionService
from hiresense.opportunities.infrastructure import OpportunitiesRepository


@dataclass(frozen=True)
class OpportunitiesBuild:
    provider: OpportunitiesProvider
    service: OpportunityIngestionService


def build_opportunities(infra: SharedInfra) -> OpportunitiesBuild:
    settings = infra.settings
    repo = OpportunitiesRepository(session_factory=infra.sync_session_factory)

    sources = []
    normalizers: dict = {}
    for name in settings.enabled_opportunity_sources:
        if name == "confs_tech":
            sources.append(
                ConfsTechAdapter(
                    infra.http_client,
                    topics=list(settings.confs_tech_topics),
                    years=list(settings.confs_tech_years),
                    base_url=settings.confs_tech_base_url,
                    timeout=settings.http_timeout,
                )
            )
            normalizers["confs_tech"] = ConfsTechNormalizer()
        elif name == "curated":
            sources.append(
                CuratedImportAdapter(
                    import_dir=settings.opportunities_import_dir,
                    filename=settings.opportunities_import_filename,
                )
            )
            normalizers["curated"] = CuratedImportNormalizer()

    service = OpportunityIngestionService(
        sources=sources,
        normalizers=normalizers,
        repository=repo,
    )
    provider = OpportunitiesProvider(service)
    return OpportunitiesBuild(provider=provider, service=service)
