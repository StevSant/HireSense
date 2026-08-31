from __future__ import annotations


class ChallengeProbeError(RuntimeError):
    """Raised when the driver cannot determine whether a challenge is present.

    Deliberately not swallowed by the driver. "I could not tell" is not the same
    answer as "there is no challenge", and this subsystem's rule is that
    under-escalating is the unacceptable direction -- proceeding would type the
    candidate's data into a form that may be gated behind a captcha.
    """
