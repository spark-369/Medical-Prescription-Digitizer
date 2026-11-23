"""AI assistant chat endpoint tests (structured JSON replies)."""

from __future__ import annotations

from app.schemas.assistant import AssistantReply
from tests.conftest import bearer, login, register, upload_prescription


def _fake_reply(monkeypatch, *, answer: str = "Hello world"):
    calls: list[list[dict]] = []

    def fake_assistant_reply(messages: list[dict]) -> AssistantReply:
        calls.append(messages)
        return AssistantReply(
            answer=answer,
            key_points=["Take it after meals"],
            follow_ups=["What about side effects?"],
        )

    monkeypatch.setattr(
        "app.api.routes.assistant.assistant_reply", fake_assistant_reply
    )
    return calls


async def test_chat_requires_authentication(client):
    response = await client.post(
        "/api/v1/assistant/chat",
        json={"message": "hi"},
    )
    assert response.status_code == 401


async def test_chat_returns_structured_reply(client, monkeypatch):
    calls = _fake_reply(monkeypatch)
    await register(client)
    token = (await login(client))["access_token"]

    response = await client.post(
        "/api/v1/assistant/chat",
        json={"message": "What should I know?"},
        headers=bearer(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Hello world"
    assert body["key_points"] == ["Take it after meals"]
    assert body["follow_ups"] == ["What about side effects?"]

    payload = calls[0]
    assert payload[-1]["content"] == "What should I know?"
    assert payload[0]["role"] == "system"


async def test_chat_grounded_in_prescription(client, monkeypatch):
    calls = _fake_reply(monkeypatch)
    await register(client)
    token = (await login(client))["access_token"]
    prescription = await upload_prescription(client, token)

    response = await client.post(
        "/api/v1/assistant/chat",
        json={
            "message": "Explain my medications",
            "prescription_id": str(prescription.id),
        },
        headers=bearer(token),
    )
    assert response.status_code == 200

    system_message = calls[0][0]["content"]
    assert "Amoxicillin" in system_message
    assert "Prescription data:" in system_message


async def test_chat_history_is_forwarded(client, monkeypatch):
    calls = _fake_reply(monkeypatch)
    await register(client)
    token = (await login(client))["access_token"]

    response = await client.post(
        "/api/v1/assistant/chat",
        json={
            "message": "and then?",
            "history": [
                {"role": "user", "content": "first question"},
                {"role": "assistant", "content": "first answer"},
            ],
        },
        headers=bearer(token),
    )
    assert response.status_code == 200
    messages = calls[0]
    assert [m["content"] for m in messages[1:]] == [
        "first question",
        "first answer",
        "and then?",
    ]


async def test_chat_rejects_invalid_payload(client):
    await register(client)
    token = (await login(client))["access_token"]
    response = await client.post(
        "/api/v1/assistant/chat",
        json={"message": ""},
        headers=bearer(token),
    )
    assert response.status_code == 422
