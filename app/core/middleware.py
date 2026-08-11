"""API Key 鉴权中间件（纯 ASGI 实现，兼容 SSE 流式响应）。

对白名单路径之外的所有请求校验 `X-API-Key` 请求头。
"""
from starlette.responses import JSONResponse

DEFAULT_EXEMPT_PATHS = {
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
}


class APIKeyAuthMiddleware:
    """校验请求头 X-API-Key 是否与配置一致。"""

    def __init__(
        self,
        app,
        api_key: str,
        exempt_paths: set[str] | None = None,
        exempt_prefixes: set[str] | None = None,
    ):
        self.app = app
        self.api_key = api_key
        self.exempt_paths = exempt_paths if exempt_paths is not None else DEFAULT_EXEMPT_PATHS
        self.exempt_prefixes = exempt_prefixes or set()

    def _is_exempt(self, path: str, method: str) -> bool:
        # CORS 预检放行
        if method.upper() == "OPTIONS":
            return True
        if path in self.exempt_paths:
            return True
        if any(path.startswith(p) for p in self.exempt_prefixes):
            return True
        return False

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "")
        if self._is_exempt(path, method):
            await self.app(scope, receive, send)
            return

        # API_KEY 为空时跳过鉴权（开发模式）
        if not self.api_key:
            await self.app(scope, receive, send)
            return

        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers", [])
        }
        api_key = headers.get("x-api-key")
        if api_key != self.api_key:
            response = JSONResponse(
                status_code=401,
                content={"detail": "无效的 API Key", "code": "UNAUTHORIZED"},
                headers={"WWW-Authenticate": "ApiKey"},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
