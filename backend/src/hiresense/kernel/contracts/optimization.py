"""Backward-compatible re-export. Import from kernel.schemas."""

from hiresense.kernel.schemas.optimization_request_dto import OptimizationRequestDTO
from hiresense.kernel.schemas.tex_diff_dto import TexDiffDTO

__all__ = ["OptimizationRequestDTO", "TexDiffDTO"]
