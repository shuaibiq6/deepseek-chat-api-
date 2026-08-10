"""对话接口测试。"""
import json

import pytest


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_chat_non_stream_creates_conversation(client):
    resp = await client.post(
        "/api/v1/chat", json={"message": "你好", "stream": False}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["conversation_id"] == 1
    assert data["reply"] == "echo:你好"
    assert data["model"] == "fake-deepseek-r1"

    lst = await client.get("/api/v1/conversations")
    items = lst.json()["items"]
    assert lst.json()["total"] == 1
    assert items[0]["message_count"] == 2
    assert items[0]["last_message"] == "echo:你好"


@pytest.mark.asyncio
async def test_chat_multi_turn_context(client):
    """多轮上下文：第二条请求应携带历史 user 消息。"""
    first = await client.post(
        "/api/v1/chat", json={"message": "我的名字是小明", "stream": False}
    )
    cid = first.json()["conversation_id"]

    second = await client.post(
        "/api/v1/chat",
        json={"conversation_id": cid, "message": "我叫什么？", "stream": False},
    )
    assert second.status_code == 200
    assert second.json()["reply"] == "echo:我叫什么？"
    assert second.json()["conversation_id"] == cid

    hist = await client.get(f"/api/v1/conversations/{cid}/messages")
    roles = [m["role"] for m in hist.json()["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]


@pytest.mark.asyncio
async def test_chat_system_prompt_and_title(client):
    message = "这是一个用于生成会话标题的测试消息，长度需要超过二十个字符"
    resp = await client.post(
        "/api/v1/chat",
        json={
            "message": message,
            "stream": False,
            "system_prompt": "你是客服助手",
        },
    )
    assert resp.status_code == 200

    conv = (await client.get("/api/v1/conversations")).json()["items"][0]
    assert conv["title"] == message[:20]  # 首条用户消息截断前 20 字符


@pytest.mark.asyncio
async def test_chat_stream_sse(client):
    async with client.stream(
        "POST", "/api/v1/chat", json={"message": "你好", "stream": True}
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        lines = [line async for line in resp.aiter_lines()]

    events = [
        json.loads(line[len("data:"):])
        for line in lines
        if line.startswith("data:")
    ]
    assert events and events[-1]["type"] == "done"
    content = "".join(e["content"] for e in events if e["type"] == "delta")
    assert content == "stream:你好"
    assert events[-1]["conversation_id"] == 1
    assert events[-1]["message_id"] == 2  # user(1) + assistant(2)


@pytest.mark.asyncio
async def test_chat_stream_persists_history(client):
    async with client.stream(
        "POST", "/api/v1/chat", json={"message": "流式消息", "stream": True}
    ) as resp:
        lines = [line async for line in resp.aiter_lines()]
    events = [
        json.loads(line[len("data:"):])
        for line in lines
        if line.startswith("data:")
    ]
    cid = events[-1]["conversation_id"]

    hist = await client.get(f"/api/v1/conversations/{cid}/messages")
    messages = hist.json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[-1]["content"] == "stream:流式消息"


@pytest.mark.asyncio
async def test_chat_validation_error(client):
    resp = await client.post("/api/v1/chat", json={"message": ""})
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_chat_unauthorized(client_no_auth):
    resp = await client_no_auth.post(
        "/api/v1/chat", json={"message": "hi", "stream": False}
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_chat_bad_api_key(client_no_auth):
    client_no_auth.headers["X-API-Key"] = "wrong-key"
    resp = await client_no_auth.post(
        "/api/v1/chat", json={"message": "hi", "stream": False}
    )
    assert resp.status_code == 401
