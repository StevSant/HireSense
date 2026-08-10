"""Cross-cutting technical layers shared by every bounded context.

Deliberately empty of re-exports: importing a submodule must not pull in
the whole subtree (that is what makes the composition layer's eager
``__init__`` a circular-import hazard). Import from the sub-package that
gives the symbol its context, e.g. ``from hiresense.shared.ports import LLMPort``.
"""
