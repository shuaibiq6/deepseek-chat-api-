"""示例客户端：演示如何调用本服务（含 SSE 流式）。

用法：
  export API_KEY=your-api-key
  python examples/client_demo.py "你好，介绍一下自己"
  python examples/client_demo.py "继续说" --conversation-id 1
  python examples/client_demo.py "你好" --no-stream
"""
import argparse
import asyncio
import json
import os

import httpx

API_BASE = os.getenv("API_BASE", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "your-api-key")


async def chat(message: str, conversation_id: int | None = None, stream: bool = True) -> None:
    headers = {"X-API-Key": API_KEY}
    payload: dict = {"message": message, "stream": stream}
    if conversation_id:
        payload["conversation_id"] = conversation_id

    url = f"{API_BASE}/api/v1/chat"

    if stream:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                print("\n[Assistant] ", end="", flush=True)
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    event = json.loads(line[len("data:"):])
                    if event["type"] == "delta":
                        print(event["content"], end="", flush=True)
                    elif event["type"] == "done":
                        print(f"\n[done] conversation_id={event['conversation_id']} "
                              f"message_id={event['message_id']}")
                    elif event["type"] == "error":
                        print(f"\n[error] {event['message']}")
        print()
    else:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            print(f"\n[Assistant] {data['reply']}")
            print(f"[conversation_id] {data['conversation_id']}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="DeepSeek Chat API 示例客户端")
    parser.add_argument("message", nargs="?", default="你好，介绍一下你自己")
    parser.add_argument("--conversation-id", type=int, default=None, help="复用会话 ID 实现多轮")
    parser.add_argument("--no-stream", action="store_true", help="关闭流式")
    args = parser.parse_args()
    await chat(args.message, args.conversation_id, stream=not args.no_stream)


if __name__ == "__main__":
    asyncio.run(main())
