"""Backward-compatible re-export. Import from hiresense.ports instead."""

from hiresense.ports.vector_store import ScoredResult, VectorStorePort

__all__ = ["ScoredResult", "VectorStorePort"]
