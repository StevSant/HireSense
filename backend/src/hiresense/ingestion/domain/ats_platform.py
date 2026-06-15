from __future__ import annotations

import enum


class AtsPlatform(str, enum.Enum):
    """Applicant-tracking-system platforms HireSense can recognise.

    The values match the `platform` strings used in `portals.yml`, so a portal's
    configured platform maps straight onto this enum. For board-sourced jobs the
    same platform is detected from the listing URL host instead.
    """

    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    WORKABLE = "workable"
    SMARTRECRUITERS = "smartrecruiters"
    RECRUITEE = "recruitee"
