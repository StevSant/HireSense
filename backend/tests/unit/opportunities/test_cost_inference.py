from __future__ import annotations

from hiresense.opportunities.domain.cost import infer_attendance_cost


def test_infer_funded_and_free() -> None:
    assert (
        infer_attendance_cost(title="Khipu", funding="Travel covered", kind="event") == "Funded"
    )
    assert infer_attendance_cost(title="Free Python Meetup", url="https://example.com") == "Free"
    assert infer_attendance_cost(kind="grant") == "Funded"


def test_infer_paid_from_ticket_urls() -> None:
    assert (
        infer_attendance_cost(
            title="XtremeAI",
            url="https://www.eventbrite.com/e/xtremeai-2026-online-conference-tickets-175",
        )
        == "Paid"
    )
    assert (
        infer_attendance_cost(title="DevOpsCon", url="https://devopscon.io/berlin/tickets")
        == "Paid"
    )


def test_infer_unknown_when_no_fee_signal() -> None:
    assert (
        infer_attendance_cost(
            title="KubeCon North America",
            url="https://events.linuxfoundation.org/kubecon",
            kind="conference",
        )
        == "Likely paid"
    )
    # CFP is about submissions; attendance is still typically ticketed.
    assert (
        infer_attendance_cost(
            title="Global Summit",
            url="https://example.com/summit",
            apply_url="https://example.com/cfp",
            kind="cfp",
        )
        == "Likely paid"
    )
    assert infer_attendance_cost(title="Mystery listing", url="https://example.com") == "Unknown"
