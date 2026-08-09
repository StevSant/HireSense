from __future__ import annotations


class EmailClassificationError(RuntimeError):
    """Raised when an inbound email could not be classified at all (the LLM call
    failed, or its response was unparseable).

    This must NOT be collapsed into ``EmailClassification(job_related=False)``:
    that value is the *verdict* "this email is not about a job application", and
    the caller drops such emails without storing a signal. Folding a failure
    into it means an LLM outage marks every arriving message as definitively
    not job-related, so rejections and interview invitations are discarded and
    never retried.

    Keeping the two apart lets each caller decide:
    ``InboxProcessingService.run()`` isolates and logs it per email, while
    ``ingest_one()`` (the ``/tracking/ingest-email`` webhook) lets it propagate
    so the route returns 500 and the provider redelivers the message.
    """
