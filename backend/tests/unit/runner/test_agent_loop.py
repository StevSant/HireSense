from hiresense.runner import AgentLoop

_BLANK_PAGE = "<html><head><title>Apply</title></head><body><p>form</p></body></html>"


class _Driver:
    def __init__(self, html=_BLANK_PAGE):
        self.page_html = html
        self.calls = []

    async def goto(self, url):
        self.calls.append(("goto", url))

    async def html(self):
        return self.page_html

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
        return "Application submitted. Thank you."

    async def close(self):
        self.calls.append(("close",))


class _Client:
    def __init__(self, actions):
        self.actions = list(actions)
        self.completed = None
        self.heartbeats = 0
        self.observations = []

    async def observe(self, attempt_id, observation):
        self.observations.append(observation)
        return self.actions.pop(0) if self.actions else {"kind": "escalate", "reason": "drained"}

    async def heartbeat(self, attempt_id):
        self.heartbeats += 1

    async def complete(self, attempt_id, status, evidence):
        self.completed = (status, evidence)

    async def artifact(self, application_id, kind):
        return f"/tmp/{kind}.pdf"


def _attempt():
    return {
        "id": "a1",
        "application_id": "app-1",
        "target_url": "https://x.test/apply",
    }


async def test_dry_run_submit_never_clicks():
    driver = _Driver()
    client = _Client([{"kind": "submit", "selector": "#go", "dry_run": True}])
    await AgentLoop(client, driver, max_steps=5).run(_attempt())
    assert ("click", "#go") not in driver.calls
    assert client.completed[0] == "submitted"
    assert client.completed[1]["dry_run"] is True
    assert "Application submitted" in client.completed[1]["confirmation_text"]


async def test_live_submit_clicks_exactly_once():
    driver = _Driver()
    client = _Client([{"kind": "submit", "selector": "#go", "dry_run": False}])
    await AgentLoop(client, driver, max_steps=5).run(_attempt())
    assert driver.calls.count(("click", "#go")) == 1
    assert client.completed[1]["dry_run"] is False


async def test_navigates_to_the_target_first():
    driver = _Driver()
    client = _Client([{"kind": "submit", "selector": "#go", "dry_run": True}])
    await AgentLoop(client, driver, max_steps=5).run(_attempt())
    assert driver.calls[0] == ("goto", "https://x.test/apply")


async def test_fill_action_types_every_field():
    driver = _Driver()
    client = _Client(
        [
            {
                "kind": "fill_fields",
                "fills": [
                    {"selector": "#a", "value": "one"},
                    {"selector": "#b", "value": "two"},
                ],
            },
            {"kind": "submit", "selector": "#go", "dry_run": True},
        ]
    )
    await AgentLoop(client, driver, max_steps=5).run(_attempt())
    assert ("fill", "#a", "one") in driver.calls
    assert ("fill", "#b", "two") in driver.calls


async def test_upload_action_fetches_the_artifact_then_attaches_it():
    driver = _Driver()
    client = _Client(
        [
            {"kind": "upload_file", "selector": "#cv", "artifact": "cv"},
            {"kind": "submit", "selector": "#go", "dry_run": True},
        ]
    )
    await AgentLoop(client, driver, max_steps=5).run(_attempt())
    assert ("upload", "#cv", "/tmp/cv.pdf") in driver.calls


async def test_step_ceiling_terminates_a_looping_form():
    driver = _Driver()
    client = _Client([{"kind": "click", "selector": "#next"}] * 10)
    await AgentLoop(client, driver, max_steps=3).run(_attempt())
    assert driver.calls.count(("click", "#next")) == 3
    assert client.completed[0] == "failed"
    assert "ceiling" in client.completed[1]["reason"]


async def test_escalate_action_ends_the_loop_without_completing():
    driver = _Driver()
    client = _Client([{"kind": "escalate", "reason": "captcha", "fields": []}])
    await AgentLoop(client, driver, max_steps=5).run(_attempt())
    # The server already moved it to escalated; the runner must not overwrite that.
    assert client.completed is None


async def test_heartbeat_is_sent_between_steps():
    driver = _Driver()
    client = _Client(
        [
            {"kind": "click", "selector": "#next"},
            {"kind": "submit", "selector": "#go", "dry_run": True},
        ]
    )
    await AgentLoop(client, driver, max_steps=5).run(_attempt())
    assert client.heartbeats == 1


async def test_observation_sent_to_the_server_is_sanitized():
    driver = _Driver("<html><body><script>alert(1)</script><p>hi</p></body></html>")
    client = _Client([{"kind": "submit", "selector": "#go", "dry_run": True}])
    await AgentLoop(client, driver, max_steps=5).run(_attempt())
    assert "alert(" not in client.observations[0]["page_text"]
