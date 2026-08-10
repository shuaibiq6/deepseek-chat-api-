"""FastAPI 应用入口。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1.endpoints import chat, history
from app.config import settings
from app.core.exceptions import AppError
from app.core.middleware import APIKeyAuthMiddleware
from app.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.AUTO_CREATE_TABLES:
        from app.core.database import init_db

        await init_db()
        logger.info("已按配置自动建表（AUTO_CREATE_TABLES=true）")
    yield


def create_app() -> FastAPI:
    setup_logging()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "本地 DeepSeek R1 对话服务：多轮上下文管理、历史持久化与 SSE 流式响应。"
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # API Key 鉴权中间件（白名单外的请求需携带 X-API-Key）
    app.add_middleware(
        APIKeyAuthMiddleware,
        api_key=settings.API_KEY,
        exempt_paths={"/health", "/docs", "/redoc", "/openapi.json"},
    )

    # 路由注册
    app.include_router(chat.router, prefix=settings.API_V1_PREFIX, tags=["对话 Chat"])
    app.include_router(history.router, prefix=settings.API_V1_PREFIX, tags=["历史 History"])

    # 健康检查
    @app.get("/health", tags=["系统"])
    async def health():
        return {
            "status": "ok",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
        }

    # 业务异常统一处理
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code},
        )

    # 参数校验异常处理
    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors(), "code": "VALIDATION_ERROR"},
        )

    return app


app = create_app()
