import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from pelumas_agent.app import create_app
from pelumas_agent.config import get_settings
from pelumas_agent.whatsapp.transport import MockTransport

SECRET = "test-secret"
APP_SECRET_NUM = "6281200000099"


def _wa_payload(wamid: str, text: str, from_phone: str = APP_SECRET_NUM) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "1",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "messages": [
                                {
                                    "from": from_phone,
                                    "id": wamid,
                                    "timestamp": "1700000000",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setenv("WA_APP_SECRET", SECRET)
    monkeypatch.setenv("WA_VERIFY_TOKEN", "verify-me")
    get_settings.cache_clear()
    transport = MockTransport()
    app = create_app(settings=get_settings(), transport=transport)
    with TestClient(app) as test_client:
        test_client.transport_mock = transport
        yield test_client
    get_settings.cache_clear()


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def test_get_verify_ok(client):
    response = client.get(
        "/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "12345"},
    )
    assert response.status_code == 200
    assert response.text == "12345"


def test_get_verify_bad_token(client):
    response = client.get(
        "/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "1"},
    )
    assert response.status_code == 403


def test_post_requires_valid_signature(client):
    body = json.dumps(_wa_payload("wamid.1", "halo")).encode()
    response = client.post(
        "/webhook", content=body, headers={"X-Hub-Signature-256": "sha256=deadbeef"}
    )
    assert response.status_code == 403

    response = client.post("/webhook", content=body)
    assert response.status_code == 403


def test_post_processes_message(client):
    body = json.dumps(_wa_payload("wamid.2", "kamu bot ya?")).encode()
    response = client.post(
        "/webhook",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    replies = client.transport_mock.to(APP_SECRET_NUM)
    assert any("AI" in reply for reply in replies)


def test_post_dedupes_wamid(client):
    body = json.dumps(_wa_payload("wamid.3", "kamu bot ya?")).encode()
    headers = {"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"}
    assert client.post("/webhook", content=body, headers=headers).json()["status"] == "ok"
    client.transport_mock.sent.clear()
    assert client.post("/webhook", content=body, headers=headers).json()["status"] == "duplicate"
    assert client.transport_mock.to(APP_SECRET_NUM) == []


def test_post_ignores_status_callbacks(client):
    body = json.dumps({"entry": [{"changes": [{"value": {"statuses": [{"id": "x"}]}}]}]}).encode()
    response = client.post(
        "/webhook",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}
