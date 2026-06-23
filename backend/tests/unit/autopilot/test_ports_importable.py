from hiresense.autopilot.domain.ports import ApplicationDrafter, DraftRepository


def test_ports_runtime_checkable():
    class _Repo:
        def add(self, draft): ...
        def list(self, limit): ...
        def exists_for_job(self, job_id): ...

    class _Drafter:
        async def draft(self, job_id): ...

    assert isinstance(_Repo(), DraftRepository)
    assert isinstance(_Drafter(), ApplicationDrafter)
