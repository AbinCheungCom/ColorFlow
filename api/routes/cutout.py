"""Cutout 抠图接口路由"""

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

from api.config import (
    ALLOWED_IMAGE_TYPES,
    COLORFLOW_MAX_FILE_SIZE,
    COLORFLOW_OUTPUT_DIR,
)
from colorflow_sdk import ColorFlowSDK
from colorflow_sdk.exceptions import CutoutError, TraceError, ValidationError

router = APIRouter()


async def _read_upload(request: Request, image: UploadFile) -> bytes:
    """校验类型与大小，受限读取上传内容（与 trace 路由同一套防护）"""
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {image.content_type}. Allowed: PNG, JPEG, WebP, BMP",
        )

    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit():
        if int(content_length) > COLORFLOW_MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max size: {COLORFLOW_MAX_FILE_SIZE // (1024 * 1024)}MB",
            )

    image_bytes = await image.read(COLORFLOW_MAX_FILE_SIZE + 1)
    if len(image_bytes) > COLORFLOW_MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {COLORFLOW_MAX_FILE_SIZE // (1024 * 1024)}MB",
        )
    return image_bytes


@router.post("/cutout")
async def cutout_image(
    request: Request,
    image: UploadFile = File(..., description="图片文件（PNG/JPG/WebP/BMP）"),
    model: str = Form("u2net", description="抠图模型"),
    allow_rmbg: bool = Form(False, description="是否放行 RMBG 系模型（BRIA 许可）"),
    alpha_matting: bool = Form(False, description="是否启用 alpha matting 边缘细化"),
):
    """
    抠图：背景移除，返回透明底 PNG

    - **model**: u2net（默认）/ silueta / isnet / birefnet-general / birefnet-2k
      （RMBG 系 bria-rmbg / birefnet-rmbg 需 allow_rmbg=true，遵守 BRIA 许可）
    - **allow_rmbg**: 默认 false，RMBG 系模型必须显式开启
    - **alpha_matting**: 毛发等精细边缘建议开启（较慢）
    """
    image_bytes = await _read_upload(request, image)

    sdk = ColorFlowSDK(output_dir=COLORFLOW_OUTPUT_DIR)
    try:
        png_bytes = sdk.cutout_bytes(
            image_bytes,
            model=model,
            allow_rmbg=allow_rmbg,
            alpha_matting=alpha_matting,
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except CutoutError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": 'attachment; filename="output.png"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/cutout-trace")
async def cutout_trace(
    request: Request,
    image: UploadFile = File(..., description="图片文件（PNG/JPG/WebP/BMP）"),
    model: str = Form("u2net", description="抠图模型"),
    allow_rmbg: bool = Form(False, description="是否放行 RMBG 系模型（BRIA 许可）"),
    alpha_matting: bool = Form(False, description="是否启用 alpha matting 边缘细化"),
    background: str = Form("255,255,255", description="描图前合成背景色 R,G,B"),
    mode: str = Form("color", description="描图模式: color/grey/human"),
    filter_speckle: int = Form(4, ge=1, le=100, description="斑点过滤阈值"),
    path_precision: int = Form(7, ge=1, le=16, description="路径精度"),
):
    """
    一键「抠图 + 描图」串联：背景移除 → 合成背景色 → SVG

    先抠出主体再描图，背景噪声不再污染 VTracer，SVG 路径更干净、颜色提取更准。
    """
    image_bytes = await _read_upload(request, image)

    # 解析背景色 "R,G,B"
    try:
        parts = [int(x.strip()) for x in background.split(",")]
        if len(parts) != 3 or any(not (0 <= v <= 255) for v in parts):
            raise ValueError
        bg = tuple(parts)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="background 格式应为 R,G,B（0-255），如 255,255,255",
        ) from None

    sdk = ColorFlowSDK(output_dir=COLORFLOW_OUTPUT_DIR)
    try:
        svg_bytes = sdk.cutout_then_trace_bytes(
            image_bytes,
            background=bg,
            model=model,
            allow_rmbg=allow_rmbg,
            alpha_matting=alpha_matting,
            mode=mode,
            filter_speckle=filter_speckle,
            path_precision=path_precision,
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except (CutoutError, TraceError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return Response(
        content=svg_bytes,
        media_type="image/svg+xml",
        headers={
            "Content-Disposition": 'attachment; filename="output.svg"',
            "X-Content-Type-Options": "nosniff",
        },
    )
