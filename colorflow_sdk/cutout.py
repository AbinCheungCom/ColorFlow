"""
ColorFlow CUTOUT 抠图模块（背景移除 → 透明底 PNG）

内核基于 rembg（MIT），模型权重许可独立，注意红线：
- 默认模型 u2net / silueta（可商用，无附加协议）
- RMBG 系模型（bria-rmbg / birefnet-rmbg）为 BRIA 许可，商用需遵守协议，
  必须显式设置 allow_rmbg=True 才会放行
"""

import io

from PIL import Image

from .exceptions import CutoutError, ValidationError

# 可商用默认模型：u2net（176MB，通用高质量）/ silueta（43MB，轻量快）/ isnet（176MB，边缘优）
# birefnet-general / birefnet-2k：BiRefNet 2024 SOTA，毛发、半透明边缘最佳，重且慢
CUTOUT_MODELS = ("u2net", "silueta", "isnet", "birefnet-general", "birefnet-2k")

# RMBG 系模型：BRIA 许可，商用需遵守协议（每月 100 万张内免费），必须显式开启
RMBG_MODELS = ("bria-rmbg", "birefnet-rmbg")

RMBG_LICENSE_NOTICE = (
    "bria-rmbg / birefnet-rmbg 模型权重为 BRIA 许可（商用需遵守其协议，"
    "每月 100 万张内免费）。如需使用请显式传入 allow_rmbg=True；"
    "商用默认请使用 u2net / silueta / isnet / birefnet-general。"
)

DEFAULT_MAX_SIDE = 4096  # 长边超过该值先等比缩小再抠图，防止大图内存峰值


def validate_model(model: str, allow_rmbg: bool = False) -> None:
    """校验模型名；RMBG 系模型未显式授权时拒绝（许可红线）"""
    if model in CUTOUT_MODELS:
        return
    if model in RMBG_MODELS:
        if not allow_rmbg:
            raise ValidationError(RMBG_LICENSE_NOTICE)
        return
    raise ValidationError(
        f"Invalid model: {model}. Must be one of {CUTOUT_MODELS + RMBG_MODELS} "
        f"(RMBG 系需 allow_rmbg=True)"
    )


def _resize_guard(image, max_side: int | None):
    """长边超过 max_side 时等比缩小，返回 (图片, 原尺寸或 None)"""
    width, height = image.size
    longest = max(width, height)
    if max_side and longest > max_side:
        scale = max_side / longest
        new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
        return image.resize(new_size), (width, height)
    return image, None


def _restore_size(image, original_size):
    """抠图结果恢复到原尺寸（保持输出与输入 1:1）"""
    if original_size:
        return image.resize(original_size)
    return image


def _run_rembg(
    image,
    model_name: str,
    alpha_matting: bool = False,
    alpha_matting_foreground_threshold: int = 240,
    alpha_matting_background_threshold: int = 10,
    alpha_matting_erode_size: int = 10,
):
    """调用 rembg.remove()（懒加载依赖），输入输出均为 PIL Image"""
    try:
        from rembg import new_session, remove
    except ImportError as e:
        raise CutoutError(
            "rembg 未安装，请执行: pip install \"colorflow-sdk[cutout]\""
        ) from e

    try:
        session = new_session(model_name)
    except Exception as e:
        raise CutoutError(
            f"抠图模型 {model_name} 加载失败（首次使用需联网下载权重，"
            f"可通过 U2NET_HOME 指定缓存目录）: {e}"
        ) from e

    # rembg 对 PIL 输入的支持随版本而异，统一转 bytes 最稳
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    try:
        result = remove(
            buf.getvalue(),
            session=session,
            alpha_matting=alpha_matting,
            alpha_matting_foreground_threshold=alpha_matting_foreground_threshold,
            alpha_matting_background_threshold=alpha_matting_background_threshold,
            alpha_matting_erode_size=alpha_matting_erode_size,
        )
    except Exception as e:
        raise CutoutError(f"rembg 抠图执行失败: {e}") from e

    return Image.open(io.BytesIO(result)).convert("RGBA")


def cutout_image(
    image,
    model: str = "u2net",
    allow_rmbg: bool = False,
    alpha_matting: bool = False,
    alpha_matting_foreground_threshold: int = 240,
    alpha_matting_background_threshold: int = 10,
    alpha_matting_erode_size: int = 10,
    max_side: int | None = DEFAULT_MAX_SIDE,
):
    """抠图主流程：PIL Image → 透明底 RGBA PIL Image"""
    validate_model(model, allow_rmbg)

    if not isinstance(image, Image.Image):
        raise ValidationError("image must be a PIL Image")

    resized, original_size = _resize_guard(image, max_side)
    result = _run_rembg(
        resized,
        model_name=model,
        alpha_matting=alpha_matting,
        alpha_matting_foreground_threshold=alpha_matting_foreground_threshold,
        alpha_matting_background_threshold=alpha_matting_background_threshold,
        alpha_matting_erode_size=alpha_matting_erode_size,
    )
    return _restore_size(result, original_size)


def composite_on_background(image, background=(255, 255, 255)):
    """透明底 RGBA 合成到背景色上（VTracer 忽略 alpha，透明像素会变黑，
    描图前必须先合成背景，默认白底贴合印刷承印物）"""
    rgba = image.convert("RGBA")
    bg = Image.new("RGB", rgba.size, background)
    bg.paste(rgba, mask=rgba.split()[3])
    return bg
