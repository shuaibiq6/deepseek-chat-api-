"""pytest 全局夹具。

- 使用 SQLite 内存库替代 MySQL，便于本地/CI 运行
- 通过依赖覆盖注入 FakeDeepSeekClient，避免真实网络调用
"""
import os

# 必须在导入 app 相关模块前设置测试环境变量
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["API_KEY"] = "test-api-key"
os.environ["DEEPSEEK_API_KEY"] = "test-deepseek-key"
os.environ["DEEPSEEK_API_BASE"] = "http://fake-deepseek"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.config import settings
from app.core.database import Base, SessionLocal, engine
from app.main import app


class FakeDeepSeekClient:
    """测试替身：回显用户最后一条消息，便于断言多轮上下文。"""

    model = "fake-deepseek-r1"

    async def chat_completion(self, messages, **kwargs):
        return f"echo:{messages[-1]['content']}"

    async def stream_chat(self, messages, **kwargs):
        text = f"stream:{messages[-1]['content']}"
        for char in text:
            yield char


def _override_client():
    return FakeDeepSeekClient()


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    """会话级：创建全部表，结束后清空。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    """函数级：每个用例前清空表数据。"""
    from app.models import Conversation, Message

    async with SessionLocal() as db:
        await db.execute(delete(Message))
        await db.execute(delete(Conversation))
        await db.commit()
    yield


@pytest_asyncio.fixture
async def client(setup_db, clean_db):
    """已注入 FakeDeepSeekClient、携带合法 API Key 的测试客户端。"""
    from app.api.v1.endpoints.chat import get_deepseek_client

    app.dependency_overrides[get_deepseek_client] = _override_client
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        c.headers["X-API-Key"] = settings.API_KEY
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client_no_auth(setup_db, clean_db):
    """未携带 API Key 的测试客户端。"""
    from app.api.v1.endpoints.chat import get_deepseek_client

    app.dependency_overrides[get_deepseek_client] = _override_client
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
    app.dependency_overrides.clear()
