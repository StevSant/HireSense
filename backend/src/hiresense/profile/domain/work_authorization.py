from enum import Enum


class WorkAuthorizationStatus(str, Enum):
    """Candidate's authorization posture for the roles they pursue."""

    AUTHORIZED = "authorized"
    REQUIRES_SPONSORSHIP = "requires_sponsorship"
    UNKNOWN = "unknown"
