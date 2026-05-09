"""ColorFlow API 配置"""
import os

# API 配置
COLORFLOW_API_KEY = os.getenv("COLORFLOW_API_KEY", "mv-p4ss-k3y-2026")
COLORFLOW_OUTPUT_DIR = os.getenv("COLORFLOW_OUTPUT_DIR", "/tmp")
COLORFLOW_TIMEOUT = int(os.getenv("COLORFLOW_TIMEOUT", "30"))
COLORFLOW_MAX_FILE_SIZE = int(os.getenv("COLORFLOW_MAX_FILE_SIZE", str(10 * 1024 * 1024)))  # 10MB

# 允许的图片格式
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/bmp"}
