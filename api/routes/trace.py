"""Trace 接口路由"""
import io
from fastapi import APIRouter, File, Form, UploadFile, HTTPException, Query
from fastapi.responses import Response

from colorflow_sdk import ColorFlowSDK
from colorflow_sdk.exceptions import ValidationError, TraceError
from api.config import ALLOWED_IMAGE_TYPES, COLORFLOW_OUTPUT_DIR, COLORFLOW_MAX_FILE_SIZE

router = APIRouter()


@router.post("/trace")
async def trace_image(
    image: UploadFile = File(..., description="图片文件（PNG/JPG/WebP）"),
    mode: str = Form("color", description="描图模式: color/grey/human"),
    colormode: str = Form("rgb8", description="颜色模式: rgb8/rgb16/mono/grey/grey16"),
    hierarchical: str = Form("stacked", description="输出层级: flat/stacked"),
    filter_speckle: int = Form(4, ge=1, le=100, description="斑点过滤阈值"),
    color_precision: int = Form(6, ge=1, le=16, description="颜色精度"),
    layer_difference: int = Form(64, ge=1, le=256, description="图层距离阈值"),
    corner_threshold: int = Form(60, ge=1, le=180, description="角点阈值"),
    length_threshold: float = Form(2.0, ge=0.1, le=100.0, description="长度阈值"),
    path_precision: int = Form(7, ge=1, le=16, description="路径精度"),
):
    """
    将上传的图片转换为 SVG 矢量格式

    - **image**: 图片文件（PNG/JPG/WebP/BMP）
    - **mode**: 描图模式
      - `color`: 彩色包装效果图、Logo、插图
      - `grey`: 灰度图、线条图、印刷稿
      - `human`: 人像、人物照片
    - **filter_speckle**: 斑点过滤阈值，越大过滤越多
    - **path_precision**: 路径精度，越高质量越大
    """
    # 校验文件类型
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {image.content_type}. Allowed: PNG, JPEG, WebP, BMP"
        )

    # 读取图片内容
    image_bytes = await image.read()

    # 检查文件大小
    if len(image_bytes) > COLORFLOW_MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {COLORFLOW_MAX_FILE_SIZE // (1024*1024)}MB"
        )

    # 推断图片格式
    ext = image.filename.split(".")[-1].lower() if image.filename else "png"
    format_map = {"jpg": "jpeg", "png": "png", "webp": "webp", "bmp": "bmp"}
    image_format = format_map.get(ext, "png")

    # 调用 SDK
    sdk = ColorFlowSDK(output_dir=COLORFLOW_OUTPUT_DIR)
    try:
        svg_bytes = sdk.trace_bytes(
            image_bytes,
            image_format=image_format,
            mode=mode,
            colormode=colormode,
            hierarchical=hierarchical,
            filter_speckle=filter_speckle,
            color_precision=color_precision,
            layer_difference=layer_difference,
            corner_threshold=corner_threshold,
            length_threshold=length_threshold,
            path_precision=path_precision,
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except TraceError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return Response(
        content=svg_bytes,
        media_type="image/svg+xml",
        headers={
            "Content-Disposition": f'attachment; filename="output.svg"',
            "X-Content-Type-Options": "nosniff",
        }
    )
