"""ColorFlow API 配置"""

import os


def _require_env(name: str) -> str:
    """读取必需的环境变量，缺失时拒绝启动（避免生产环境使用弱默认值）。"""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required env var: {name}. "
            f"请在部署时通过环境变量注入（如 docker-compose 或容器编排配置）。"
        )
    return value


# API 配置
COLORFLOW_API_KEY = _require_env("COLORFLOW_API_KEY")
COLORFLOW_OUTPUT_DIR = os.getenv("COLORFLOW_OUTPUT_DIR", "/tmp")
COLORFLOW_MAX_FILE_SIZE = int(
    os.getenv("COLORFLOW_MAX_FILE_SIZE", str(10 * 1024 * 1024))
)  # 10MB
# CORS 允许的来源（逗号分隔；"*" 表示全部）
COLORFLOW_ALLOWED_ORIGINS = os.getenv("COLORFLOW_ALLOWED_ORIGINS", "*").split(",")
# 是否暴露交互式 API 文档（生产环境建议关闭）
COLORFLOW_ENABLE_DOCS = os.getenv("COLORFLOW_ENABLE_DOCS", "true").lower() != "false"

# 允许的图片格式
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/bmp"}
