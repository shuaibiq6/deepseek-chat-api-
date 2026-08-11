"""本地模拟 DeepSeek（OpenAI 兼容）上游服务。

用于在无真实 API Key / 无网络时，联调本服务与前端：
  - 支持 /chat/completions 非流式与流式（SSE）两种响应
  - 回显最后一条用户消息，便于验证多轮上下文

用法：
  python scripts/mock_deepseek_server.py            # 默认 0.0.0.0:8001
  python scripts/mock_deepseek_server.py --port 9000

配合后端联调：
  将 .env 中 DEEPSEEK_API_BASE=http://localhost:8001/v1 指向本服务。
"""
import argparse
import json
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI(title="Mock DeepSeek Server")


@app.get("/v1/models")
async def models():
    return {"object": "list", "data": [{"id": "deepseek-r1", "object": "model"}]}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    messages = body.get("messages", [])
    stream = bool(body.get("stream", False))
    model = body.get("model", "deepseek-r1")
    # 回显最后一条用户消息，构造一个可读的回复
    last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    reply = f"【模拟回复】收到：{last}\n\n- 模型：{model}\n- 上下文消息数：{len(messages)}\n这是一段用于验证流式输出的模拟内容。"

    if not stream:
        return JSONResponse(
            {
                "id": "mock-cmpl",
                "object": "chat.completion",
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": reply},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }
        )

    # 流式：按字符逐个推送 delta
    async def gen():
        def chunk(delta: str, finish: str | None = None):
            return (
                "data: "
                + json.dumps(
                    {
                        "id": "mock-cmpl",
                        "object": "chat.completion.chunk",
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"role": "assistant", "content": delta},
                                "finish_reason": finish,
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )

        for ch in reply:
            yield chunk(ch)
            await _sleep(0.01)
        yield chunk("", "stop")
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )


async def _sleep(seconds: float):
    import asyncio

    await asyncio.sleep(seconds)


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    print(f"Mock DeepSeek server on http://{args.host}:{args.port}/v1")
    uvicorn.run(app, host=args.host, port=args.port)
