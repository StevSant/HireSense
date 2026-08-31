"""The driver-side captcha probe.

`page.content()` serializes neither shadow roots nor cross-origin frame
contents, so a challenge rendered into either is invisible to the DOM
serializer. The driver can see both, so the loop asks it and ORs the answer in.
"""

from hiresense.runner import AgentLoop

_PAGE = "<html><head><title>Apply</title></head><body><p>form</p></body></html>"


class _Driver:
    """Driver whose challenge probe is configurable."""

    def __init__(self, challenge=False, boom=False):
        self._challenge = challenge
        self._boom = boom
        self.calls = []
        self.probes = 0

    async def goto(self, url):
        self.calls.append(("goto", url))

    async def html(self):
        return _PAGE

    async def url(self):
        return "https://x.test/apply"

    async def title(self):
        return "Apply"

    async def fill(self, selector, value):
        self.calls.append(("fill", selector, value))

    async def click(self, selector):
        self.calls.append(("click", selector))

    async def upload(self, selector, path):
        self.calls.append(("upload", selector, path))

    async def text(self):
        return "done"

    async def challenge_present(self):
        self.probes += 1
        if self._boom:
            raise RuntimeError("cdp gone")
        return self._challenge

    async def close(self):
        pass


class _LegacyDriver(_Driver):
    """A driver written before the probe existed."""

    challenge_present = None

    def __init__(self):
        super().__init__()
        del self.__dict__["probes"]
        self.probes = 0


class _Client:
    def __init__(self, actions):
        self.actions = list(actions)
        self.observations = []
        self.completed = None

    async def observe(self, attempt_id, observation):
        self.observations.append(observation)
        return self.actions.pop(0) if self.actions else {"kind": "escalate", "reason": "drained"}

    async def heartbeat(self, attempt_id):
        pass

    async def complete(self, attempt_id, status, evidence):
        self.completed = (status, evidence)

    async def artifact(self, application_id, kind):
        return None


def _attempt():
    return {"id": "a1", "application_id": "app-1", "target_url": "https://x.test/apply"}


async def test_driver_reported_challenge_reaches_the_server():
    """The HTML has no captcha marker at all; only the driver knows."""
    driver = _Driver(challenge=True)
    client = _Client([{"kind": "escalate", "reason": "captcha", "fields": []}])
    await AgentLoop(client, driver, max_steps=3).run(_attempt())
    assert client.observations[0]["captcha_detected"] is True


async def test_clean_page_stays_clean():
    driver = _Driver(challenge=False)
    client = _Client([{"kind": "submit", "selector": "#go", "dry_run": True}])
    await AgentLoop(client, driver, max_steps=3).run(_attempt())
    assert client.observations[0]["captcha_detected"] is False


async def test_probe_failure_is_not_fatal():
    """A driver error must degrade to 'no challenge', never abort the run."""
    driver = _Driver(boom=True)
    client = _Client([{"kind": "submit", "selector": "#go", "dry_run": True}])
    await AgentLoop(client, driver, max_steps=3).run(_attempt())
    assert client.observations[0]["captcha_detected"] is False
    assert client.completed[0] == "submitted"


async def test_driver_without_a_probe_still_works():
    driver = _LegacyDriver()
    client = _Client([{"kind": "submit", "selector": "#go", "dry_run": True}])
    await AgentLoop(client, driver, max_steps=3).run(_attempt())
    assert client.observations[0]["captcha_detected"] is False


async def test_probe_is_skipped_when_the_html_already_shows_a_challenge():
    """No point paying for a round-trip the serializer already answered."""

    class _CaptchaHtmlDriver(_Driver):
        async def html(self):
            return (
                '<html><body><iframe src="https://google.com/recaptcha/api2/bframe?k=x">'
                "</iframe></body></html>"
            )

    driver = _CaptchaHtmlDriver(challenge=False)
    client = _Client([{"kind": "escalate", "reason": "captcha", "fields": []}])
    await AgentLoop(client, driver, max_steps=3).run(_attempt())
    assert client.observations[0]["captcha_detected"] is True
    assert driver.probes == 0
