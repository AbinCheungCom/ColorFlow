"""API KEY 认证中间件"""
import secrets
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from api.config import COLORFLOW_API_KEY


class AuthMiddleware(BaseHTTPMiddleware):
    """API KEY 认证中间件"""

    async def dispatch(self, request: Request, call_next):
        # 仅对 /api/ 路径进行认证
        if request.url.path.startswith("/api/"):
            # 跳过 /api/health
            if request.url.path == "/api/health":
                return await call_next(request)

            api_key = request.headers.get("x-api-key")
            if not api_key:
                raise HTTPException(status_code=401, detail="Missing API key")

            # 常量时间比较，防止时序攻击
            if not secrets.compare_digest(api_key, COLORFLOW_API_KEY):
                raise HTTPException(status_code=401, detail="Invalid API key")

        response = await call_next(request)
        return response
