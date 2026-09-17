"""应用配置模块

从环境变量读取配置，开发时用 .env 文件，生产环境用系统环境变量。
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # ===== 基础配置 =====
    APP_NAME: str = "ask-api"
    APP_VERSION: str = "0.3.0"
    DEBUG: bool = True

    # ===== 数据库配置 =====
    DATABASE_URL: str = "sqlite+aiosqlite:///./ask_api.db"

    # ===== 数据回收配置 =====
    MESSAGE_RETENTION_DAYS: int = 7
    CLEANUP_INTERVAL_HOURS: int = 24

    # ===== 安全配置 =====
    DAILY_REQUEST_LIMIT: int = 200
    CORS_ORIGINS: list[str] = ["*"]
    # 管理员 API Key（生成邀请码等管理操作需要）
    ADMIN_API_KEY: str = "ask-admin-secret"
    # 限流开关
    RATE_LIMIT_ENABLED: bool = True

    # ===== AI 模型配置 =====
    # 智谱 GLM-4-Flash（免费模型，0.1元/百万tokens）
    LLM_MODEL: str = "glm-4-flash-250414"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


# 全局配置单例
settings = Settings()
