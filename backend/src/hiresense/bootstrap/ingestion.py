from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import hiresense
from hiresense.ingestion.adapters import (
    AshbyAdapter,
    CSVImportAdapter,
    GetOnBoardAdapter,
    GreenhouseAdapter,
    HimalayasAdapter,
    HNHiringAdapter,
    JobicyAdapter,
    LeverAdapter,
    LinkedInAdapter,
    RemoteOKAdapter,
    RemotiveAdapter,
    WeWorkRemotelyAdapter,
)
from hiresense.ingestion.api.provider import IngestionProvider
from hiresense.ingestion.domain import (
    IngestionOrchestrator,
    JobEmbeddingIndexer,
    JobRevalidationService,
    PortalScanner,
    load_portals_config,
)
from hiresense.ingestion.domain.embedding_backfill_service import EmbeddingBackfillService
from hiresense.ingestion.domain.normalizers import (
    AshbyNormalizer,
    CSVNormalizer,
    GetOnBoardNormalizer,
    GreenhouseNormalizer,
    HimalayasNormalizer,
    HNHiringNormalizer,
    JobicyNormalizer,
    LeverNormalizer,
    LinkedInNormalizer,
    RemoteOKNormalizer,
    RemotiveNormalizer,
    WeWorkRemotelyNormalizer,
)
from hiresense.ingestion.domain.quick_scoring_service import QuickScoringService
from hiresense.ingestion.infrastructure import JobMatchCacheRepository, JobsRepository
from hiresense.matching.domain.deep_analysis_service import DeepAnalysisService
from hiresense.bootstrap.shared_infra import SharedInfra


@dataclass(frozen=True)
class IngestionBuild:
    provider: IngestionProvider
    orchestrator: IngestionOrchestrator


def build_ingestion(infra: SharedInfra, tracked: Callable[[str], Any], *, preference_query: Any = None) -> IngestionBuild:
    s = infra.settings
    http_client = infra.http_client

    sources = []
    normalizers = {}
    for source_name in s.enabled_job_sources:
        if source_name == "remotive":
            sources.append(RemotiveAdapter(http_client=http_client))
            normalizers["remotive"] = RemotiveNormalizer()
        elif source_name == "remoteok":
            sources.append(RemoteOKAdapter(http_client=http_client))
            normalizers["remoteok"] = RemoteOKNormalizer()
        elif source_name == "csv":
            sources.append(CSVImportAdapter())
            normalizers["csv"] = CSVNormalizer()
        elif source_name == "jobicy":
            sources.append(JobicyAdapter(http_client=http_client, base_url=s.jobicy_api_url))
            normalizers["jobicy"] = JobicyNormalizer()
        elif source_name == "himalayas":
            sources.append(HimalayasAdapter(http_client=http_client, base_url=s.himalayas_api_url))
            normalizers["himalayas"] = HimalayasNormalizer()
        elif source_name == "hn_hiring":
            sources.append(HNHiringAdapter(http_client=http_client, base_url=s.hn_algolia_api_url))
            normalizers["hn_hiring"] = HNHiringNormalizer()
        elif source_name == "weworkremotely":
            sources.append(
                WeWorkRemotelyAdapter(http_client=http_client, rss_url=s.weworkremotely_rss_url)
            )
            normalizers["weworkremotely"] = WeWorkRemotelyNormalizer()
        elif source_name == "getonboard":
            sources.append(
                GetOnBoardAdapter(
                    http_client=http_client,
                    base_url=s.getonboard_api_url,
                    categories=s.getonboard_categories,
                )
            )
            normalizers["getonboard"] = GetOnBoardNormalizer()
        elif source_name == "linkedin":
            sources.append(
                LinkedInAdapter(
                    http_client=http_client,
                    base_url=s.linkedin_jobs_url,
                    detail_concurrency=s.linkedin_detail_concurrency,
                    detail_delay=s.linkedin_detail_delay,
                )
            )
            normalizers["linkedin"] = LinkedInNormalizer()

    boards_jobs_repo = JobsRepository(session_factory=infra.sync_session_factory, bucket="boards")
    portals_jobs_repo = JobsRepository(session_factory=infra.sync_session_factory, bucket="portals")

    # Persist embeddings of newly ingested jobs into the vector store (when one is
    # configured) so semantic search survives restarts. Per-bucket so search can
    # filter by tab. None when no vector store is wired (e.g. tests) → no-op.
    boards_indexer = (
        JobEmbeddingIndexer(infra.embedding, infra.vector_store, bucket="boards")
        if infra.vector_store is not None
        else None
    )
    portals_indexer = (
        JobEmbeddingIndexer(infra.embedding, infra.vector_store, bucket="portals")
        if infra.vector_store is not None
        else None
    )

    ingestion_orchestrator = IngestionOrchestrator(
        sources=sources,
        normalizers=normalizers,
        event_bus=infra.event_bus,
        cooldown_seconds=s.ingestion_cooldown_seconds,
        repository=boards_jobs_repo,
        retention_days=s.ingestion_job_retention_days,
        indexer=boards_indexer,
        closure_miss_threshold=s.job_closure_miss_threshold,
    )

    # URL-probe revalidation sweep for the boards bucket. Snapshot sources
    # (portals) get disappearance-based closure during ingestion, so the sweep
    # only targets feed/search sources whose listings stay live after closing.
    # hn_hiring is excluded (frozen HN comment URLs never 404 / carry markers);
    # csv has no live URL to probe.
    revalidation_sources = [
        name
        for name in s.enabled_job_sources
        if name not in ("hn_hiring", "csv")
    ]
    revalidation_service = JobRevalidationService(
        http_client=http_client,
        repository=boards_jobs_repo,
        indexer=boards_indexer,
        sources=revalidation_sources,
        markers=s.job_closed_markers,
        batch=s.job_revalidation_batch,
        concurrency=s.job_revalidation_concurrency,
        delay=s.job_revalidation_delay,
    )

    # Resolve the portals config relative to the hiresense package root (not
    # this module), preserving the original create_app() behaviour.
    portals_config_path = Path(hiresense.__file__).parent / s.portals_config_path
    portals_config = load_portals_config(portals_config_path)

    portal_adapters = {
        "greenhouse": GreenhouseAdapter(
            http_client=http_client,
            base_url=s.greenhouse_api_url,
            timeout=s.portal_scan_timeout,
        ),
        "lever": LeverAdapter(
            http_client=http_client,
            base_url=s.lever_api_url,
            timeout=s.portal_scan_timeout,
        ),
        "ashby": AshbyAdapter(
            http_client=http_client,
            base_url=s.ashby_api_url,
            timeout=s.portal_scan_timeout,
        ),
    }

    portal_normalizers = {
        "greenhouse": GreenhouseNormalizer(),
        "lever": LeverNormalizer(),
        "ashby": AshbyNormalizer(),
    }

    portal_scanner = PortalScanner(
        config=portals_config,
        adapters=portal_adapters,
        normalizers=portal_normalizers,
        event_bus=infra.event_bus,
        repository=portals_jobs_repo,
        retention_days=s.ingestion_job_retention_days,
        indexer=portals_indexer,
        closure_miss_threshold=s.job_closure_miss_threshold,
    )

    from hiresense.ingestion.domain.semantic_pre_ranker import SemanticPreRanker
    from hiresense.ingestion.domain.semantic_scoring_service import SemanticScoringService

    semantic_scoring = SemanticScoringService(embedding_port=infra.embedding)

    # SemanticPreRanker wires vector store + embedding for global ANN pre-ranking.
    # When vector store is None (no pgvector configured), pre_ranker is still
    # constructed — its own passthrough logic handles the None vector_store case.
    pre_ranker = SemanticPreRanker(
        infra.vector_store,
        infra.embedding,
        top_k_cap=s.prerank_top_k_cap,
        skill_weight=s.prerank_weight_skill,
        semantic_weight=s.prerank_weight_semantic,
        preference=preference_query,
    )

    match_cache_repo = JobMatchCacheRepository(session_factory=infra.sync_session_factory)
    quick_scoring = QuickScoringService(
        llm=tracked("match_quick_scorer"),
        cache_repo=match_cache_repo,
        batch_size=s.match_quick_batch_size,
        job_char_limit=s.match_quick_job_char_limit,
    )
    deep_analysis = DeepAnalysisService(
        llm=tracked("match_deep_analyzer"),
        cache_repo=match_cache_repo,
        job_char_limit=s.match_deep_job_char_limit,
    )

    # Backfill service: re-embeds all pre-existing jobs into pgvector on demand.
    # Uses the same embedding + vector_store as the per-bucket indexers.
    # None when no vector store is configured (graceful no-op at runtime).
    backfill_service = EmbeddingBackfillService(
        boards_repo=boards_jobs_repo,
        portals_repo=portals_jobs_repo,
        embedding=infra.embedding,
        vector_store=infra.vector_store,
    )

    provider = IngestionProvider(
        orchestrator=ingestion_orchestrator,
        portal_scanner=portal_scanner,
        portals_config=portals_config,
        semantic_scoring=semantic_scoring,
        quick_scoring=quick_scoring,
        deep_analysis=deep_analysis,
        pre_ranker=pre_ranker,
        revalidation_service=revalidation_service,
        backfill_service=backfill_service,
    )
    return IngestionBuild(provider=provider, orchestrator=ingestion_orchestrator)
