"""历史与会话管理接口测试。"""
import pytest


async def _make_chat(client, message: str, **kwargs):
    resp = await client.post(
        "/api/v1/chat", json={"message": message, "stream": False, **kwargs}
    )
    assert resp.status_code == 200
    return resp.json()["conversation_id"]


@pytest.mark.asyncio
async def test_list_conversations_empty(client):
    resp = await client.get("/api/v1/conversations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_conversations_pagination(client):
    ids = set()
    for i in range(3):
        ids.add(await _make_chat(client, f"消息 {i}"))

    resp = await client.get("/api/v1/conversations", params={"limit": 2})
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2

    resp2 = await client.get("/api/v1/conversations", params={"limit": 2, "offset": 2})
    assert len(resp2.json()["items"]) == 1


@pytest.mark.asyncio
async def test_get_history_returns_messages_in_order(client):
    cid = await _make_chat(client, "第一问")
    await client.post(
        "/api/v1/chat",
        json={"conversation_id": cid, "message": "第二问", "stream": False},
    )

    resp = await client.get(f"/api/v1/conversations/{cid}/messages")
    assert resp.status_code == 200
    data = resp.json()
    assert data["conversation_id"] == cid
    assert data["total"] == 4
    contents = [m["content"] for m in data["messages"]]
    assert contents == ["第一问", "echo:第一问", "第二问", "echo:第二问"]


@pytest.mark.asyncio
async def test_get_history_not_found(client):
    resp = await client.get("/api/v1/conversations/999/messages")
    assert resp.status_code == 404
    assert resp.json()["code"] == "CONVERSATION_NOT_FOUND"


@pytest.mark.asyncio
async def test_chat_with_missing_conversation_404(client):
    resp = await client.post(
        "/api/v1/chat",
        json={"conversation_id": 999, "message": "hi", "stream": False},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "CONVERSATION_NOT_FOUND"


@pytest.mark.asyncio
async def test_delete_conversation(client):
    cid = await _make_chat(client, "待删除")
    resp = await client.delete(f"/api/v1/conversations/{cid}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # 删除后历史不可再访问
    resp2 = await client.get(f"/api/v1/conversations/{cid}/messages")
    assert resp2.status_code == 404

    lst = await client.get("/api/v1/conversations")
    assert lst.json()["total"] == 0


@pytest.mark.asyncio
async def test_delete_conversation_not_found(client):
    resp = await client.delete("/api/v1/conversations/999")
    assert resp.status_code == 404
    assert resp.json()["code"] == "CONVERSATION_NOT_FOUND"
