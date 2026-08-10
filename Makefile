.PHONY: install run revision migrate db-init test docker-up docker-down

## 安装全部依赖（含开发依赖）
install:
	pip install -r requirements.txt -r requirements-dev.txt

## 本地启动（热重载）
run:
	uvicorn app.main:app --reload --port 8000

## 生成新迁移（用法：make revision m="添加字段")
revision:
	alembic revision --autogenerate -m "$(m)"

## 应用迁移到最新版本
migrate:
	alembic upgrade head

## 初始化数据库（建库 + 迁移）
db-init:
	python scripts/init_db.py

## 运行测试
test:
	pytest -v

## Docker Compose 一键启动（FastAPI + MySQL）
docker-up:
	docker compose -f docker/docker-compose.yml up --build -d

## 停止并移除容器
docker-down:
	docker compose -f docker/docker-compose.yml down
