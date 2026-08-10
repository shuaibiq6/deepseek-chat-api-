"""历史接口：会话列表 / 会话历史 / 删除会话。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.chat import (
    ConversationListResponse,
    ConversationOut,
    DeleteResponse,
    HistoryResponse,
    MessageOut,
)
from app.services.conversation import ConversationService

router = APIRouter()


@router.get(
    "/conversations",
    response_model=ConversationListResponse,
    summary="会话列表（分页）",
)
async def list_conversations(
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: AsyncSession = Depends(get_db),
):
    total, items = await ConversationService.list_conversations(
        db, limit=limit, offset=offset
    )
    return ConversationListResponse(
        total=total, items=[ConversationOut(**item) for item in items]
    )


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=HistoryResponse,
    summary="获取会话历史消息",
)
async def get_history(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
):
    conv, messages = await ConversationService.get_history(db, conversation_id)
    return HistoryResponse(
        conversation_id=conv.id,
        total=len(messages),
        messages=[MessageOut.model_validate(m) for m in messages],
    )


@router.delete(
    "/conversations/{conversation_id}",
    response_model=DeleteResponse,
    summary="删除会话（级联删除其消息）",
)
async def delete_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
):
    await ConversationService.delete(db, conversation_id)
    return DeleteResponse(conversation_id=conversation_id)
