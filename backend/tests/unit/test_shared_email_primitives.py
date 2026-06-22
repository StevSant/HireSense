from hiresense.adapters import SmtpEmailSender
from hiresense.kernel import EmailMessage
from hiresense.ports import EmailSenderPort, EmailUnavailableError

# Back-compat: outreach paths must resolve to the SAME objects.
from hiresense.outreach.domain import EmailMessage as OutreachEmailMessage
from hiresense.outreach.domain import EmailUnavailableError as OutreachErr
from hiresense.outreach.infrastructure import SmtpEmailSender as OutreachSender
from hiresense.outreach.ports import EmailSenderPort as OutreachPort


def test_shared_symbols_importable_and_constructible():
    msg = EmailMessage(to="a@b.com", subject="s", body="b")
    assert (msg.to, msg.subject, msg.body) == ("a@b.com", "s", "b")
    assert issubclass(EmailUnavailableError, RuntimeError)


def test_outreach_reexports_are_identical_objects():
    assert OutreachEmailMessage is EmailMessage
    assert OutreachErr is EmailUnavailableError
    assert OutreachSender is SmtpEmailSender
    assert OutreachPort is EmailSenderPort


def test_smtp_sender_raises_when_unconfigured():
    sender = SmtpEmailSender(host="", port=587, username="", password="", from_email="", use_tls=True)
    try:
        sender.send(EmailMessage(to="a@b.com", subject="s", body="b"))
        assert False, "expected EmailUnavailableError"
    except EmailUnavailableError:
        pass
