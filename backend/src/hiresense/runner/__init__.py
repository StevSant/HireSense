"""The local auto-apply runner.

A standalone client process that drives the candidate's own browser. It talks
to HireSense over HTTP only and imports nothing from any module's domain layer,
so it can run on a laptop while the backend runs anywhere.
"""

from hiresense.runner.agent_loop import AgentLoop
from hiresense.runner.browser_driver import BrowserDriver
from hiresense.runner.client import SubmissionClient
from hiresense.runner.dom_serializer import serialize_dom

__all__ = ["AgentLoop", "BrowserDriver", "SubmissionClient", "serialize_dom"]
