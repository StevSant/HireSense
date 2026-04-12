"""Backward-compatible re-export. Import from hiresense.ports instead."""

from hiresense.ports.latex_compiler import CompilationError, LaTeXCompilerPort

__all__ = ["CompilationError", "LaTeXCompilerPort"]
