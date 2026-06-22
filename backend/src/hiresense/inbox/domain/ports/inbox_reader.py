from __future__ import annotations

from typing import Protocol, runtime_checkable

from hiresense.inbox.domain.inbound_email import InboundEmail


@runtime_checkable
class InboxReaderPort(Protocol):
    """Reads unseen emails from a mailbox. Returns [] when disabled/unreachable."""

    def fetch_unseen(self) -> list[InboundEmail]: ...
