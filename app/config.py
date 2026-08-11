"""配置管理：使用 Pydantic Settings 从环境变量 / .env 文件加载配置。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """应用配置。

    优先级：环境变量 > .env 文件 > 代码默认值。
    """

    # ---- 应用基础信息 ----
    APP_NAME: str = "DeepSeek Chat API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    # 是否在应用启动时自动建表（开发便捷；生产建议使用 Alembic 迁移）
    AUTO_CREATE_TABLES: bool = True

    # ---- 本服务对外鉴权（客户端需携带 X-API-Key 请求头）----
    API_KEY: str = ""

    # ---- 数据库（SQLAlchemy 异步 URL）----
    DATABASE_URL: str = "mysql+aiomysql://deepseek:deepseek@localhost:3306/deepseek_chat"

    # ---- DeepSeek 上游配置（OpenAI 兼容协议）----
    # 可指向官方 API（https://api.deepseek.com）或本地 vLLM/Ollama 等兼容服务
    DEEPSEEK_API_KEY: str = "sk-xxxx"
    DEEPSEEK_API_BASE: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_TIMEOUT: float = 60.0


    # ---- 对话默认生成参数 ----
    DEFAULT_MAX_TOKENS: int = 2048
    DEFAULT_TEMPERATURE: float = 0.7

    # ---- 跨域（前端独立部署时放开；默认允许全部）----
    CORS_ORIGINS: list[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
