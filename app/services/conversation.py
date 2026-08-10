"""会话与消息管理服务。"""
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConversationNotFoundError
from app.models import Conversation, Message


class ConversationService:
    """会话与消息的业务逻辑。"""

    DEFAULT_TITLE = "新对话"

    @staticmethod
    async def get_or_create(db: AsyncSession, conversation_id: int | None) -> Conversation:
        """根据 ID 获取会话；ID 为空则新建会话。"""
        if conversation_id is not None:
            return await ConversationService.get(db, conversation_id)
        conv = Conversation(title=ConversationService.DEFAULT_TITLE)
        db.add(conv)
        await db.flush()
        return conv

    @staticmethod
    async def get(db: AsyncSession, conversation_id: int) -> Conversation:
        conv = await db.get(Conversation, conversation_id)
        if conv is None:
            raise ConversationNotFoundError()
        return conv

    @staticmethod
    async def add_message(
        db: AsyncSession, conversation_id: int, role: str, content: str
    ) -> Message:
        """持久化一条消息；用户消息用于生成会话标题。"""
        msg = Message(conversation_id=conversation_id, role=role, content=content)
        db.add(msg)

        await db.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=func.now())
        )
        if role == "user":
            conv = await db.get(Conversation, conversation_id)
            if conv is not None and conv.title == ConversationService.DEFAULT_TITLE:
                conv.title = content[:20] or ConversationService.DEFAULT_TITLE

        await db.commit()
        await db.refresh(msg)
        return msg

    @staticmethod
    async def build_messages(
        db: AsyncSession,
        conversation_id: int,
        system_prompt: str | None = None,
    ) -> list[dict[str, str]]:
        """将数据库历史消息转换为 DeepSeek messages 上下文（多轮上下文管理）。"""
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id)
        )
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for m in result.scalars().all():
            if m.role in {"system", "user", "assistant"}:
                messages.append({"role": m.role, "content": m.content})
        return messages

    @staticmethod
    async def list_conversations(
        db: AsyncSession, limit: int = 20, offset: int = 0
    ) -> tuple[int, list[dict[str, Any]]]:
        """分页列出会话，附带消息数与最后一条消息预览。"""
        total = (
            await db.execute(select(func.count(Conversation.id)))
        ).scalar_one()

        result = await db.execute(
            select(Conversation)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        convs = list(result.scalars().all())
        if not convs:
            return total, []

        ids = [c.id for c in convs]
        rows = (
            await db.execute(
                select(Message.conversation_id, Message.content)
                .where(Message.conversation_id.in_(ids))
                .order_by(Message.id)
            )
        ).all()

        last_by_conv: dict[int, str] = {}
        count_by_conv: dict[int, int] = {}
        for cid, content in rows:
            count_by_conv[cid] = count_by_conv.get(cid, 0) + 1
            last_by_conv[cid] = content  # 按 id 升序遍历，最终留下最新一条

        items = [
            {
                "id": c.id,
                "title": c.title,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
                "message_count": count_by_conv.get(c.id, 0),
                "last_message": last_by_conv.get(c.id),
            }
            for c in convs
        ]
        return total, items

    @staticmethod
    async def get_history(
        db: AsyncSession, conversation_id: int
    ) -> tuple[Conversation, list[Message]]:
        """获取某个会话的完整历史消息（按时间正序）。"""
        conv = await ConversationService.get(db, conversation_id)
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id)
        )
        return conv, list(result.scalars().all())

    @staticmethod
    async def delete(db: AsyncSession, conversation_id: int) -> None:
        """删除会话及其全部消息（级联删除）。"""
        conv = await ConversationService.get(db, conversation_id)
        await db.delete(conv)
        await db.commit()
