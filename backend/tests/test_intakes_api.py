import uuid

import pytest
from httpx import AsyncClient

from tests.factories import make_conversation


@pytest.mark.asyncio
async def test_create_intake_success(admin_client: AsyncClient) -> None:
    conversation = await make_conversation(admin_client)
    resp = await admin_client.post("/api/v1/intakes", json={"conversation_id": conversation["id"], "concern": "acne"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "in_progress"
    assert body["concern"] == "acne"


@pytest.mark.asyncio
async def test_create_intake_nonexistent_conversation_returns_404(admin_client: AsyncClient) -> None:
    resp = await admin_client.post("/api/v1/intakes", json={"conversation_id": str(uuid.uuid4())})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_second_intake_for_same_conversation_returns_409(admin_client: AsyncClient) -> None:
    conversation = await make_conversation(admin_client)
    first = await admin_client.post("/api/v1/intakes", json={"conversation_id": conversation["id"]})
    assert first.status_code == 201

    second = await admin_client.post("/api/v1/intakes", json={"conversation_id": conversation["id"]})
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_get_intake_not_found_returns_404(admin_client: AsyncClient) -> None:
    resp = await admin_client.get(f"/api/v1/intakes/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_intake_status_and_fields(admin_client: AsyncClient) -> None:
    conversation = await make_conversation(admin_client)
    intake = (await admin_client.post("/api/v1/intakes", json={"conversation_id": conversation["id"]})).json()

    resp = await admin_client.patch(
        f"/api/v1/intakes/{intake['id']}", json={"status": "complete", "body_area": "face", "goal": "reduce_wrinkles"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "complete"
    assert body["body_area"] == "face"
    assert body["goal"] == "reduce_wrinkles"


@pytest.mark.asyncio
async def test_list_intakes_filter_by_conversation_id(admin_client: AsyncClient) -> None:
    conversation = await make_conversation(admin_client)
    intake = (await admin_client.post("/api/v1/intakes", json={"conversation_id": conversation["id"]})).json()

    resp = await admin_client.get(f"/api/v1/intakes?conversation_id={conversation['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == intake["id"]
