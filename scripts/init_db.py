"""数据库初始化脚本。

功能：
  1. 若数据库不存在则自动创建（MySQL / SQLite 自动处理）；
  2. 执行 Alembic 迁移至最新版本（upgrade head）。

用法：
  python scripts/init_db.py
"""
import os
import sys

# 确保可导入项目根目录包
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.config import settings

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_database_if_not_exists() -> None:
    """连接 MySQL 服务器，若目标库不存在则创建。"""
    url = settings.DATABASE_URL
    if not url.startswith("mysql"):
        print(f"[init_db] 非 MySQL 数据源，跳过自动建库：{url}")
        return

    sync_url = url.replace("mysql+aiomysql://", "mysql+pymysql://", 1)
    db_name = sync_url.rsplit("/", 1)[-1]
    server_url = sync_url[: sync_url.rfind("/")]

    engine = sa.create_engine(server_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            exists = conn.execute(
                sa.text(
                    "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA "
                    "WHERE SCHEMA_NAME = :name"
                ),
                {"name": db_name},
            ).scalar()
            if not exists:
                conn.execute(
                    sa.text(
                        f"CREATE DATABASE `{db_name}` "
                        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                    )
                )
                print(f"[init_db] 已创建数据库: {db_name}")
            else:
                print(f"[init_db] 数据库已存在: {db_name}")
    finally:
        engine.dispose()


def run_migrations() -> None:
    """执行 Alembic 迁移至最新版本。"""
    cfg = Config(os.path.join(PROJECT_ROOT, "alembic.ini"))
    cfg.set_main_option(
        "script_location", os.path.join(PROJECT_ROOT, "alembic")
    )
    cfg.set_main_option(
        "sqlalchemy.url",
        settings.DATABASE_URL.replace(
            "mysql+aiomysql://", "mysql+pymysql://", 1
        ),
    )
    command.upgrade(cfg, "head")
    print("[init_db] Alembic 迁移完成")


if __name__ == "__main__":
    create_database_if_not_exists()
    run_migrations()
