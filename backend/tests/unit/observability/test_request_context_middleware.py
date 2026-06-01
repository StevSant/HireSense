from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hiresense.observability.middleware import RequestContextMiddleware
from hiresense.observability import request_id_var


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/echo")
    async def echo() -> dict[str, str]:
        return {"request_id": request_id_var.get() or ""}

    return app


def test_generates_request_id_and_echoes_header():
    client = TestClient(_app())
    resp = client.get("/echo")
    assert resp.status_code == 200
    rid = resp.headers["X-Request-ID"]
    assert rid
    assert resp.json()["request_id"] == rid


def test_honors_inbound_request_id():
    client = TestClient(_app())
    resp = client.get("/echo", headers={"X-Request-ID": "client-supplied"})
    assert resp.headers["X-Request-ID"] == "client-supplied"
    assert resp.json()["request_id"] == "client-supplied"
