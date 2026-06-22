import uuid

from hiresense.inbox.domain import ApplicationMatcher, EmailClassification, EmailSignalKind
from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication


def _app(company, status=ApplicationStatus.APPLIED):
    return TrackedApplication(id=uuid.uuid4(), title="Dev", company=company, status=status.value)


def _classification(kind, company, confidence=0.9):
    return EmailClassification(job_related=True, kind=kind, company=company,
                               role="Dev", confidence=confidence)


def test_matches_active_app_by_company_and_maps_status():
    app = _app("Acme Corp")
    matcher = ApplicationMatcher(min_confidence=0.5)
    matched_id, proposed = matcher.match(_classification(EmailSignalKind.REJECTION, "Acme"), [app])
    assert matched_id == app.id
    assert proposed == ApplicationStatus.REJECTED.value


def test_interview_maps_to_interviewing():
    app = _app("Globex")
    matched_id, proposed = ApplicationMatcher(0.5).match(
        _classification(EmailSignalKind.INTERVIEW, "Globex"), [app])
    assert proposed == ApplicationStatus.INTERVIEWING.value


def test_no_company_match_returns_none():
    app = _app("Acme")
    matched_id, proposed = ApplicationMatcher(0.5).match(
        _classification(EmailSignalKind.REJECTION, "Initech"), [app])
    assert (matched_id, proposed) == (None, None)


def test_low_confidence_returns_none():
    app = _app("Acme")
    matched_id, proposed = ApplicationMatcher(0.5).match(
        _classification(EmailSignalKind.REJECTION, "Acme", confidence=0.2), [app])
    assert (matched_id, proposed) == (None, None)


def test_other_kind_returns_none():
    app = _app("Acme")
    matched_id, proposed = ApplicationMatcher(0.5).match(
        _classification(EmailSignalKind.OTHER, "Acme"), [app])
    assert (matched_id, proposed) == (None, None)


def test_ambiguous_multiple_matches_returns_none():
    apps = [_app("Acme"), _app("Acme Inc")]
    matched_id, proposed = ApplicationMatcher(0.5).match(
        _classification(EmailSignalKind.REJECTION, "Acme"), apps)
    assert (matched_id, proposed) == (None, None)
