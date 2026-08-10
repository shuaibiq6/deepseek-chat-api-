"""对话相关 Pydantic 模型。"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["system", "user", "assistant"]


class ChatRequest(BaseModel):
    """发起对话的请求体。"""

    message: str = Field(..., min_length=1, max_length=20000, description="用户输入内容")
    conversation_id: int | None = Field(
        None, description="会话 ID；为空则自动新建会话"
    )
    stream: bool = Field(False, description="是否以 SSE 流式返回")
    system_prompt: str | None = Field(
        None, max_length=2000, description="可选的系统提示词"
    )
    max_tokens: int | None = Field(None, ge=1, le=8192, description="生成最大 token 数")
    temperature: float | None = Field(None, ge=0.0, le=2.0, description="采样温度")


class ChatResponse(BaseModel):
    """非流式对话响应。"""

    conversation_id: int
    message_id: int
    reply: str
    model: str


class MessageOut(BaseModel):
    """消息输出模型（从 ORM 读取）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    role: Role
    content: str
    created_at: datetime


class ConversationOut(BaseModel):
    """会话列表项。"""

    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    last_message: str | None = None


class ConversationListResponse(BaseModel):
    """会话列表响应。"""

    total: int
    items: list[ConversationOut]


class HistoryResponse(BaseModel):
    """会话历史响应。"""

    conversation_id: int
    total: int
    messages: list[MessageOut]


class DeleteResponse(BaseModel):
    """删除会话响应。"""

    ok: bool = True
    conversation_id: int
