"""
ColorFlow API 服务入口
FastAPI + Uvicorn
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.middleware.auth import AuthMiddleware
from api.routes import trace

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("colorflow-api")

# FastAPI 应用
app = FastAPI(
    title="ColorFlow API",
    description="AI Agent 矢量描图 API — 位图 → SVG",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS（按需配置）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 认证中间件
app.add_middleware(AuthMiddleware)

# 注册路由
app.include_router(trace.router, prefix="/api/v1", tags=["Vector Trace"])


@app.get("/api/health", tags=["Health"])
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "colorflow-api", "version": "0.1.0"}


@app.get("/", tags=["Root"])
async def root():
    """根路径"""
    return {
        "service": "ColorFlow API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
