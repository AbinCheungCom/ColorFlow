"""API KEY 认证中间件"""

import secrets

from fastapi import Request
from fastapi.responses import JSONResponse
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
                # 注意：BaseHTTPMiddleware 中 raise HTTPException 会作为异常传播
                # （得到 500 而非 401），必须显式返回响应
                return JSONResponse(status_code=401, content={"detail": "Missing API key"})

            # 先转 bytes 再恒定时间比较：
            # secrets.compare_digest 对 str 要求 ASCII，非 ASCII 头会抛 TypeError（导致 500）
            if not secrets.compare_digest(
                api_key.encode("utf-8"), COLORFLOW_API_KEY.encode("utf-8")
            ):
                return JSONResponse(
                    status_code=401, content={"detail": "Invalid API key"}
                )

        return await call_next(request)
