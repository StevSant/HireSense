from __future__ import annotations

import enum


class ApplyAccess(str, enum.Enum):
    """Whether the candidate can actually reach the employer's application form.

    A source can be perfectly good at *listing* jobs and still be useless for
    *applying* to them. This is a property of the board, not of an individual
    posting, so it is resolved from the source capability registry rather than
    persisted per job.

    DIRECT           — the stored URL reaches the employer (or the board's own
                       free application form) with no wall in between.
    ACCOUNT_REQUIRED — applying needs a free account on the board
                       (We Work Remotely, Himalayas, Get on Board, LinkedIn,
                       Work at a Startup).
    PAID_REQUIRED    — the apply hop is behind a paid subscription.
    UNKNOWN          — not audited, or the board's behaviour varies per posting.
    """

    DIRECT = "direct"
    ACCOUNT_REQUIRED = "account_required"
    PAID_REQUIRED = "paid_required"
    UNKNOWN = "unknown"
