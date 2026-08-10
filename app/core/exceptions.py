"""自定义业务异常体系，统一映射为 HTTP 错误响应。"""


class AppError(Exception):
    """业务异常基类。"""

    status_code: int = 400
    code: str = "APP_ERROR"
    message: str = "请求处理失败"

    def __init__(self, message: str | None = None, status_code: int | None = None):
        self.message = message or self.message
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    message = "资源不存在"


class ConversationNotFoundError(NotFoundError):
    code = "CONVERSATION_NOT_FOUND"
    message = "会话不存在"


class AuthError(AppError):
    status_code = 401
    code = "UNAUTHORIZED"
    message = "API Key 无效"


class UpstreamError(AppError):
    status_code = 502
    code = "UPSTREAM_ERROR"
    message = "DeepSeek 上游服务调用失败"
