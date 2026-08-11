# DeepSeek Chat API

基于本地 DeepSeek R1 大模型的 API 对话服务，封装为标准化 RESTful API，支持多轮上下文管理、对话历史持久化与 SSE 流式响应。

## 技术栈

- **FastAPI** — Web 框架，异步高性能
- **DeepSeek API** — 模型调用（OpenAI 兼容协议，可指向官方 API 或本地 vLLM / Ollama）
- **SQLAlchemy 2.0** — 异步 ORM（async + aiomysql）
- **MySQL** — 数据持久化
- **Alembic** — 数据库迁移
- **SSE 流式** — Server-Sent Events 逐 token 输出
- **Docker Compose** — FastAPI + MySQL 一键编排
- **pytest** — 测试覆盖
- **前端** — 原生 HTML/CSS/JS 单页应用（零构建、随后端同源部署，含深色主题）

## 快速开始

### 1. 环境准备

```bash
# 复制环境配置
cp .env.example .env
# 修改 .env 中的 DEEPSEEK_API_KEY / DEEPSEEK_API_BASE / DEEPSEEK_MODEL

# 安装依赖
pip install -r requirements.txt -r requirements-dev.txt
```

### 2. 启动 MySQL（Docker）

```bash
docker compose -f docker/docker-compose.yml up -d db
```

### 3. 初始化数据库并启动

```bash
# 方式 A：初始化脚本（建库 + 迁移）
python scripts/init_db.py
# 方式 B：Alembic 手动迁移
# alembic upgrade head

uvicorn app.main:app --reload --port 8000
```

### 4. Docker Compose 一键部署

```bash
make docker-up
# 或
docker compose -f docker/docker-compose.yml up --build -d
```

访问 Swagger 文档：http://localhost:8000/docs

## RESTful 接口（4 个）

所有业务接口需携带请求头 `X-API-Key: <你的API_KEY>`。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/v1/chat` | 发起对话（`stream=true` 时 SSE 流式） |
| GET | `/api/v1/conversations` | 会话列表（分页） |
| GET | `/api/v1/conversations/{id}/messages` | 会话历史消息 |
| DELETE | `/api/v1/conversations/{id}` | 删除会话（级联删除消息） |

系统接口：`GET /health` 健康检查（免鉴权）。

### 对话示例

```bash
export API_KEY=your-api-key

# 非流式
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" -H "X-API-Key: $API_KEY" \
  -d '{"message": "你好，介绍一下自己", "stream": false}'

# SSE 流式
curl -N -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" -H "X-API-Key: $API_KEY" \
  -d '{"message": "你好", "stream": true}'

# 多轮对话（携带 conversation_id 复用上下文）
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" -H "X-API-Key: $API_KEY" \
  -d '{"conversation_id": 1, "message": "继续上一话题", "stream": false}'
```

或使用内置示例客户端：

```bash
python examples/client_demo.py "你好"
python examples/client_demo.py "继续说" --conversation-id 1
```

## SSE 流式协议

响应头：`Content-Type: text/event-stream`，每帧格式 `data: {json}\n\n`：

```text
data: {"type": "delta", "content": "你"}
data: {"type": "delta", "content": "好"}
data: {"type": "done", "conversation_id": 1, "message_id": 2, "content": "你好", "model": "deepseek-chat"}
```

- `delta`：增量片段
- `done`：生成完成（含会话/消息 ID）
- `error`：流式链路出错

## 前端界面

项目内置一套完整的单页 Web 前端（`frontend/`），随后端同源部署，启动后端后直接访问 **http://localhost:8000/** 即可使用。

### 功能一览（覆盖后端全部接口）

| 界面入口 | 后端接口 | 说明 |
| --- | --- | --- |
| 底部输入框（流式开关开） | `POST /api/v1/chat`（stream=true） | SSE 流式逐字输出 |
| 底部输入框（流式开关关） | `POST /api/v1/chat`（stream=false） | 非流式 JSON 回复 |
| 侧栏会话列表 | `GET /api/v1/conversations` | 分页加载 + 标题/消息数/最后消息预览 |
| 点击会话 | `GET /api/v1/conversations/{id}/messages` | 查看历史消息 |
| 会话项 🗑 按钮 | `DELETE /api/v1/conversations/{id}` | 删除会话（带确认弹窗） |
| 左上角服务状态 | `GET /health` | 实时在线状态 |

### 子功能跳转

- **＋ 新建对话**：清空当前视图，发送时自动创建新会话（不携带 conversation_id）
- **📋 系统提示词**：设置随每次请求发送的 `system_prompt`
- **🎛 生成参数**：调节 `temperature` 与 `max_tokens`
- **⚙ 设置**：API 地址 / API Key / 默认流式 / 界面主题
- **🌓 主题**：浅色 / 深色切换
- **⟳ 刷新 / 加载更多**：会话列表刷新与分页

### 使用说明

```bash
# 后端已自动挂载前端，直接访问：
#   http://localhost:8000/
# 独立部署前端（需后端开启 CORS）：
cd frontend && python -m http.server 8080
# 然后在「⚙ 设置」中把 API 地址填为 http://localhost:8000
```

无真实 DeepSeek Key 时可本地联调：

```bash
# 终端1：启动模拟上游（OpenAI 兼容，端口 8001）
python scripts/mock_deepseek_server.py
# 终端2：后端指向模拟上游后启动
$env:DEEPSEEK_API_BASE="http://127.0.0.1:8001/v1"
uvicorn app.main:app --reload
```

## 测试

```bash
pytest -v
# 或
make test
```

测试使用 SQLite 内存库 + FakeDeepSeekClient 注入，无需真实网络与 MySQL，覆盖：鉴权、对话、多轮上下文、流式 SSE、会话增删查等核心业务。

## 项目结构

```
deepseek-chat-api/
├── app/
│   ├── main.py                 # FastAPI 应用入口
│   ├── config.py               # 配置管理(Pydantic Settings)
│   ├── models/                 # SQLAlchemy 数据模型
│   │   ├── conversation.py     # 对话表
│   │   └── message.py          # 消息表
│   ├── schemas/                # Pydantic 请求/响应模型
│   │   └── chat.py
│   ├── api/v1/endpoints/       # 路由层
│   │   ├── chat.py             # 对话接口
│   │   └── history.py          # 历史接口
│   ├── services/               # 业务逻辑层
│   │   ├── deepseek.py         # DeepSeek API 调用
│   │   └── conversation.py     # 对话管理服务
│   ├── core/                   # 核心组件
│   │   ├── database.py         # 数据库连接
│   │   ├── middleware.py       # API Key 鉴权中间件
│   │   └── exceptions.py       # 自定义异常
│   └── utils/logger.py         # 日志配置
├── alembic/                    # 数据库迁移
├── tests/                      # pytest 测试
├── frontend/                   # 前端单页应用（随后端部署）
│   ├── index.html
│   ├── css/style.css
│   └── js/{api,app}.js
├── docker/                     # Dockerfile / docker-compose.yml
├── scripts/init_db.py          # 初始化脚本
├── scripts/mock_deepseek_server.py  # 本地模拟 DeepSeek 上游（联调用）
├── examples/client_demo.py     # 示例客户端
├── docs/项目技术详述.txt        # 项目技术详述
├── requirements.txt
└── ...
```

## 常见问题

- **本地模型接入**：将 `.env` 中 `DEEPSEEK_API_BASE` 指向本地 OpenAI 兼容服务（如 vLLM：`http://localhost:8001/v1`），`DEEPSEEK_MODEL` 改为 `deepseek-r1`。
- **自动建表 vs 迁移**：`AUTO_CREATE_TABLES=true` 时启动自动建表（开发便捷）；生产建议关闭并统一使用 Alembic 迁移。
