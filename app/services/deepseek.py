"""DeepSeek（OpenAI 兼容协议）调用封装层。

- 非流式：``chat_completion`` 返回完整回复
- 流式：``stream_chat`` 通过 SSE 逐片段 yield 增量内容
可指向官方 API 或本地 vLLM / Ollama 等 OpenAI 兼容服务。
"""
import json
import logging
from typing import Any, AsyncIterator

import httpx

from app.config import settings
from app.core.exceptions import UpstreamError

logger = logging.getLogger(__name__)


class DeepSeekClient:
    """封装 Chat Completions API 的异步客户端。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ):
        self.api_key = api_key or settings.DEEPSEEK_API_KEY
        self.base_url = (base_url or settings.DEEPSEEK_API_BASE).rstrip("/")
        self.model = model or settings.DEEPSEEK_MODEL
        self.timeout = timeout or settings.DEEPSEEK_TIMEOUT

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _endpoint(base_url: str) -> str:
        return f"{base_url}/chat/completions"

    def _payload(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool = False,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
        return payload

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """非流式对话，返回完整回复文本。"""
        url = self._endpoint(self.base_url)
        payload = self._payload(
            messages, stream=False, max_tokens=max_tokens, temperature=temperature
        )
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload, headers=self._headers)
                resp.raise_for_status()
                data = resp.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPError as exc:
            logger.exception("DeepSeek 非流式调用失败")
            raise UpstreamError(f"DeepSeek API 调用失败: {exc}") from exc
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise UpstreamError(f"DeepSeek 响应格式异常: {exc}") from exc

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        """流式对话，逐个 yield 增量文本片段。"""
        url = self._endpoint(self.base_url)
        payload = self._payload(
            messages, stream=True, max_tokens=max_tokens, temperature=temperature
        )
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST", url, json=payload, headers=self._headers
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        raw = line[len("data:"):].strip()
                        if raw == "[DONE]":
                            break
                        try:
                            obj = json.loads(raw)
                            delta = obj["choices"][0]["delta"].get("content")
                        except (KeyError, IndexError, json.JSONDecodeError):
                            continue
                        if delta:
                            yield delta
        except httpx.HTTPError as exc:
            logger.exception("DeepSeek 流式调用失败")
            raise UpstreamError(f"DeepSeek 流式调用失败: {exc}") from exc
