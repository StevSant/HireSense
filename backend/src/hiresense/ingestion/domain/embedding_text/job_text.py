from __future__ import annotations

from hiresense.ingestion.domain.models import NormalizedJob

# Cap on the text embedded per job (title + skills + description). Kept in ONE
# place so index-time (JobEmbeddingIndexer) and query-time (SemanticScoringService)
# job text are byte-identical — otherwise ANN scores and in-memory cosine scores
# would silently disagree (#161).
_JOB_TEXT_CHAR_LIMIT = 4000


def job_text(job: NormalizedJob) -> str:
    """Deterministic embedding text for a job: title + skills + description.

    Both the index-time indexer and the query-time scorer call this, so the two
    embeddings of the same job are always computed from identical input.
    """
    parts = [job.title, " ".join(job.skills), job.description]
    return "\n".join(p for p in parts if p)[:_JOB_TEXT_CHAR_LIMIT]
