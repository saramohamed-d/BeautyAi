import uuid

import pytest
from httpx import AsyncClient

from tests.factories import make_conversation, make_patient


@pytest.mark.asyncio
async def test_create_conversation_success(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/conversations", json={"channel": "web", "language": "ar"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "active"
    assert body["patient_id"] is None


@pytest.mark.asyncio
async def test_create_conversation_nonexistent_patient_returns_404(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/conversations", json={"patient_id": str(uuid.uuid4())})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_conversation_not_found_returns_404(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/conversations/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_conversation_includes_messages(client: AsyncClient) -> None:
    conversation = await make_conversation(client)
    await client.post(f"/api/v1/conversations/{conversation['id']}/messages", json={"role": "user", "content": "hi"})

    resp = await client.get(f"/api/v1/conversations/{conversation['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["messages"]) == 1
    assert body["messages"][0]["content"] == "hi"


@pytest.mark.asyncio
async def test_add_message_to_nonexistent_conversation_returns_404(client: AsyncClient) -> None:
    resp = await client.post(
        f"/api/v1/conversations/{uuid.uuid4()}/messages", json={"role": "user", "content": "hi"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_messages_paginated(client: AsyncClient) -> None:
    conversation = await make_conversation(client)
    for i in range(3):
        await client.post(
            f"/api/v1/conversations/{conversation['id']}/messages",
            json={"role": "user", "content": f"message {i}"},
        )

    resp = await client.get(f"/api/v1/conversations/{conversation['id']}/messages?page_size=2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


@pytest.mark.asyncio
async def test_update_conversation_status(client: AsyncClient) -> None:
    conversation = await make_conversation(client)
    resp = await client.patch(f"/api/v1/conversations/{conversation['id']}", json={"status": "completed"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_list_conversations_filter_by_channel(client: AsyncClient) -> None:
    await make_conversation(client, channel="whatsapp")
    resp = await client.get("/api/v1/conversations?channel=whatsapp")
    assert resp.status_code == 200
    assert all(c["channel"] == "whatsapp" for c in resp.json()["items"])
