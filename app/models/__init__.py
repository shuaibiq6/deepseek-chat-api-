"""SQLAlchemy 数据模型统一入口。"""
from app.models.conversation import Conversation
from app.models.message import Message

__all__ = ["Conversation", "Message"]
