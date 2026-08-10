"""对话接口：POST /api/v1/chat（支持 SSE 流式）。"""
import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import SessionLocal, get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.conversation import ConversationService
from app.services.deepseek import DeepSeekClient

logger = logging.getLogger(__name__)

router = APIRouter()


def get_deepseek_client() -> DeepSeekClient:
    """FastAPI 依赖：提供 DeepSeek 客户端（便于测试替换）。"""
    return DeepSeekClient()


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="发起对话（非流式 / SSE 流式）",
    description=(
        "向指定会话发送一条用户消息并获取模型回复。\n"
        "`stream=true` 时以 `text/event-stream` 返回增量内容；否则返回完整 JSON。\n"
        "不传 `conversation_id` 会自动新建会话。"
    ),
)
async def chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    client: DeepSeekClient = Depends(get_deepseek_client),
):
    # 流式：在生成器内部独立管理会话，避免依赖生命周期与长连接冲突
    if payload.stream:
        return StreamingResponse(
            _stream_events(payload, client),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # 非流式
    conv = await ConversationService.get_or_create(db, payload.conversation_id)
    await ConversationService.add_message(db, conv.id, "user", payload.message)
    messages = await ConversationService.build_messages(db, conv.id, payload.system_prompt)

    max_tokens = payload.max_tokens or settings.DEFAULT_MAX_TOKENS
    temperature = (
        payload.temperature
        if payload.temperature is not None
        else settings.DEFAULT_TEMPERATURE
    )
    reply = await client.chat_completion(
        messages, max_tokens=max_tokens, temperature=temperature
    )
    msg = await ConversationService.add_message(db, conv.id, "assistant", reply)

    return ChatResponse(
        conversation_id=conv.id, message_id=msg.id, reply=reply, model=client.model
    )


async def _stream_events(payload: ChatRequest, client: DeepSeekClient):
    """SSE 事件生成器。

    事件协议（每行 `data: {json}\\n\\n`）：
      - ``{"type": "delta", "content": "..."}``  增量片段
      - ``{"type": "done", "conversation_id":..., "message_id":..., "content":...}``  完成
      - ``{"type": "error", "message": "..."}``  出错
    """
    async with SessionLocal() as db:
        conv = await ConversationService.get_or_create(db, payload.conversation_id)
        await ConversationService.add_message(db, conv.id, "user", payload.message)
        messages = await ConversationService.build_messages(
            db, conv.id, payload.system_prompt
        )

        max_tokens = payload.max_tokens or settings.DEFAULT_MAX_TOKENS
        temperature = (
            payload.temperature
            if payload.temperature is not None
            else settings.DEFAULT_TEMPERATURE
        )

        full = ""
        try:
            async for chunk in client.stream_chat(
                messages, max_tokens=max_tokens, temperature=temperature
            ):
                full += chunk
                yield _sse({"type": "delta", "content": chunk})

            msg = await ConversationService.add_message(db, conv.id, "assistant", full)
            yield _sse(
                {
                    "type": "done",
                    "conversation_id": conv.id,
                    "message_id": msg.id,
                    "content": full,
                    "model": client.model,
                }
            )
        except Exception as exc:  # noqa: BLE001  流式链路内兜底
            logger.exception("流式对话失败")
            yield _sse({"type": "error", "message": str(exc)})


def _sse(event: dict) -> str:
    """将事件对象编码为一行 SSE data 帧。"""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
