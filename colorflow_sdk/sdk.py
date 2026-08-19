"""
ColorFlow Python SDK
供 AI Agent 直接调用，将位图转换为 SVG
"""

import os
import tempfile
from uuid import uuid4

import vtracer

from .exceptions import PrintError, TraceError, ValidationError


class ColorFlowSDK:
    """
    ColorFlow Python SDK
    供 AI Agent 直接调用，将位图转换为 SVG
    """

    MODES = ("color", "grey", "human")
    COLOR_MODES = ("rgb8", "rgb16", "mono", "grey", "grey16")
    HIERARCHICAL_MODES = ("flat", "stacked")

    def __init__(self, output_dir: str = "/tmp"):
        self.output_dir = output_dir
        self._validate_output_dir()

    def _validate_output_dir(self):
        """确保输出目录存在"""
        os.makedirs(self.output_dir, exist_ok=True)

    def _validate_path(self, path: str, must_exist: bool = True) -> None:
        """校验文件路径"""
        if not path or not isinstance(path, str):
            raise ValidationError(f"Invalid path: {path}")

        if must_exist and not os.path.exists(path):
            raise ValidationError(f"Input file not found: {path}")

        # 规范化后若仍逃逸到当前目录之外（形如 ../../x 或 a/../..），视为路径遍历。
        # 用 normpath 而非字符串包含判断，避免误伤 folder..png 这类正常文件名。
        normalized = os.path.normpath(path)
        if normalized.startswith(".."):
            raise ValidationError(f"Path traversal not allowed: {path}")

    def _validate_mode(self, mode: str) -> None:
        """校验 mode 参数"""
        if mode not in self.MODES:
            raise ValidationError(f"Invalid mode: {mode}. Must be one of {self.MODES}")

    def _validate_colormode(self, colormode: str) -> None:
        """校验 colormode 参数"""
        if colormode not in self.COLOR_MODES:
            raise ValidationError(
                f"Invalid colormode: {colormode}. Must be one of {self.COLOR_MODES}"
            )

    def _validate_hierarchical(self, hierarchical: str) -> None:
        """校验 hierarchical 参数"""
        if hierarchical not in self.HIERARCHICAL_MODES:
            raise ValidationError(
                f"Invalid hierarchical: {hierarchical}. Must be one of {self.HIERARCHICAL_MODES}"
            )

    def _validate_range(
        self, name: str, value: int, min_val: int, max_val: int
    ) -> None:
        """校验数值范围"""
        if not isinstance(value, int):
            raise ValidationError(
                f"{name} must be an integer, got {type(value).__name__}"
            )
        if not (min_val <= value <= max_val):
            raise ValidationError(
                f"{name} must be between {min_val} and {max_val}, got {value}"
            )

    def _validate_float_range(
        self, name: str, value: float, min_val: float, max_val: float
    ) -> None:
        """校验浮点数范围"""
        if not isinstance(value, (int, float)):
            raise ValidationError(
                f"{name} must be a number, got {type(value).__name__}"
            )
        if not (min_val <= value <= max_val):
            raise ValidationError(
                f"{name} must be between {min_val} and {max_val}, got {value}"
            )

    def _prepare_input_image(self, image_path: str, mode: str, colormode: str):
        """vtracer 0.6.x Python 绑定的 mode/colormode 参数失效（上游 bug），
        改为在输入侧预处理实现：
        - mode=grey / colormode=grey|grey16 → 输入灰度化
        - colormode=mono                    → 输入二值化
        - mode=color                        → posterize 色块化（VTracer 对平滑渐变
          无边界可循会塌缩成单一暗色，posterize 制造色阶边界让彩色得以保留）

        Returns:
            (处理后的图片路径, 是否临时文件需清理)
        """
        needs_grey = mode == "grey" or colormode in ("grey", "grey16")
        needs_mono = colormode == "mono"
        needs_posterize = mode == "color" and not (needs_grey or needs_mono)
        if not (needs_grey or needs_mono or needs_posterize):
            return image_path, False

        try:
            from PIL import Image, ImageOps
        except ImportError:
            # 无 Pillow 时退回原图，不阻断流程
            return image_path, False

        try:
            img = Image.open(image_path)
            if needs_mono:
                img = ImageOps.grayscale(img).point(lambda p: 255 if p > 128 else 0)
            elif needs_grey:
                img = ImageOps.grayscale(img)
            else:
                # bits=4：每通道 16 级，足够细不破坏色块插画，又能救活平滑渐变
                img = ImageOps.posterize(img.convert("RGB"), bits=4)
        except Exception:
            return image_path, False

        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        try:
            img.convert("RGB").save(tmp.name, format="PNG")
        except Exception:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)
            return image_path, False
        return tmp.name, True

    def trace(
        self,
        image_path: str,
        mode: str = "color",
        colormode: str = "rgb8",
        hierarchical: str = "stacked",
        filter_speckle: int = 4,
        color_precision: int = 6,
        layer_difference: int = 64,
        corner_threshold: int = 60,
        length_threshold: float = 2.0,
        path_precision: int = 7,
        max_iterations: int = 10,
        splice_threshold: int = 45,
    ) -> str:
        """
        将位图转为 SVG（落盘模式）

        Args:
            image_path: 输入图片路径（PNG/JPG/WebP）
            mode: 描图模式 - color（彩色）| grey（灰度）| human（人像）
            colormode: 颜色模式 - rgb8 | rgb16 | mono | grey | grey16
            hierarchical: 输出层级 - flat（平面）| stacked（堆叠）
            filter_speckle: 斑点过滤阈值（1-100），越大过滤越多
            color_precision: 颜色精度（1-16）
            layer_difference: 图层距离阈值（1-256）
            corner_threshold: 角点阈值（1-180）
            length_threshold: 长度阈值（0.1-100）
            path_precision: 路径精度（1-16），越高质量越大
            max_iterations: 最大迭代次数（固定10）
            splice_threshold: 拼接阈值（固定45）

        Returns:
            输出 SVG 文件路径

        Raises:
            ValidationError: 参数校验失败
            TraceError: VTracer 执行失败
        """
        # 参数校验
        self._validate_path(image_path)
        self._validate_mode(mode)
        self._validate_colormode(colormode)
        self._validate_hierarchical(hierarchical)
        self._validate_range("filter_speckle", filter_speckle, 1, 100)
        self._validate_range("color_precision", color_precision, 1, 16)
        self._validate_range("layer_difference", layer_difference, 1, 256)
        self._validate_range("corner_threshold", corner_threshold, 1, 180)
        self._validate_float_range("length_threshold", length_threshold, 0.1, 100.0)
        self._validate_range("path_precision", path_precision, 1, 16)

        # 生成输出路径
        output_filename = f"colorflow_{uuid4()}.svg"
        output_path = os.path.join(self.output_dir, output_filename)

        # 调用 VTracer（mode/colormode 在绑定层失效，已在输入侧预处理补偿）
        prepared_path, is_temp = self._prepare_input_image(
            image_path, mode, colormode
        )
        try:
            vtracer.convert_image_to_svg_py(
                image_path=prepared_path,
                out_path=output_path,
                colormode=colormode,
                hierarchical=hierarchical,
                mode=mode,
                filter_speckle=filter_speckle,
                color_precision=color_precision,
                layer_difference=layer_difference,
                corner_threshold=corner_threshold,
                length_threshold=length_threshold,
                max_iterations=max_iterations,
                splice_threshold=splice_threshold,
                path_precision=path_precision,
            )
        except Exception as e:
            raise TraceError(f"VTracer execution failed: {e}") from e
        finally:
            if is_temp and os.path.exists(prepared_path):
                os.unlink(prepared_path)

        # 校验输出
        if not os.path.exists(output_path):
            raise TraceError("VTracer execution failed: output file not created")

        return output_path

    def trace_bytes(
        self, image_bytes: bytes, image_format: str = "png", **kwargs
    ) -> bytes:
        """
        将位图转为 SVG（内存模式，不落盘）

        Args:
            image_bytes: 图片字节数据
            image_format: 图片格式（png/jpg/webp）
            **kwargs: 同 trace() 的参数

        Returns:
            SVG 文件字节数据
        """
        if not isinstance(image_bytes, bytes):
            raise ValidationError("image_bytes must be bytes")

        with tempfile.NamedTemporaryFile(
            suffix=f".{image_format}", delete=False
        ) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name

        try:
            svg_path = self.trace(tmp_path, **kwargs)
            # 先读取内容，再清理（避免返回时文件已被删除）
            with open(svg_path, "rb") as f:
                svg_bytes = f.read()
        finally:
            # 清理临时输入文件
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            # 清理 SVG 输出
            if "svg_path" in locals() and os.path.exists(svg_path):
                os.unlink(svg_path)

        return svg_bytes

    def trace_with_retry(
        self,
        image_path: str,
        max_retries: int = 3,
        mode: str = "color",
        **kwargs,
    ) -> str:
        """
        带降级重试的 VTracer 调用
        按 color -> grey -> human 顺序降级

        Args:
            image_path: 输入图片路径
            max_retries: 最大尝试次数（含降级；不超过剩余可用 mode 数）
            mode: 初始描图模式，失败时按 MODES 顺序降级到下一个
            **kwargs: 同 trace() 的参数（mode 已为独立参数，不要重复传入）

        Returns:
            输出 SVG 文件路径
        """
        self._validate_mode(mode)
        # 兼容旧调用：若 kwargs 中仍残留 mode（如 dict 解包传入），以显式参数为准
        kwargs.pop("mode", None)

        last_error = None
        start_idx = self.MODES.index(mode)
        # 至少尝试 1 次，且不超出 modes 列表尾部
        attempts = min(max(max_retries, 1), len(self.MODES) - start_idx)

        for offset in range(attempts):
            current_mode = self.MODES[start_idx + offset]
            try:
                return self.trace(image_path, mode=current_mode, **kwargs)
            except TraceError as e:
                last_error = e
                continue
            except ValidationError:
                raise  # 参数错误不重试

        raise TraceError(
            f"VTracer failed after {attempts} retries, last error: {last_error}"
        ) from last_error

    @staticmethod
    def get_version() -> str:
        """获取 VTracer 版本"""
        return getattr(vtracer, "__version__", "unknown")

    def export_print(
        self,
        image_path: str,
        output_path: str,
        width_mm: float,
        height_mm: float,
        bleed_mm: float = 3.0,
        mode: str = "color",
        path_precision: int = 10,
        **trace_kwargs,
    ) -> str:
        """
        位图 → 生产印刷级 CMYK PDF（含出血 + 物理尺寸 + BleedBox）。

        Args:
            image_path: 输入位图路径
            output_path: 输出 PDF 路径（.pdf）
            width_mm: 成品宽度（毫米，>0）
            height_mm: 成品高度（毫米，>0）
            bleed_mm: 出血（毫米，>=0，印刷标准 3）
            mode: 描图模式（color/grey/human）
            path_precision: 路径精度（印刷级建议 10+，默认 7）
            **trace_kwargs: 透传 trace() 其余参数（filter_speckle 等）

        Returns:
            输出 PDF 文件路径

        Raises:
            ValidationError: 参数非法
            TraceError: 描图失败
            PrintError: PDF 构建失败 / 缺依赖
        """
        # 1. 参数校验
        for name, val in (("width_mm", width_mm), ("height_mm", height_mm)):
            if not isinstance(val, (int, float)) or val <= 0:
                raise ValidationError(f"{name} must be > 0, got {val}")
        if not isinstance(bleed_mm, (int, float)) or bleed_mm < 0:
            raise ValidationError(f"bleed_mm must be >= 0, got {bleed_mm}")
        if not output_path.lower().endswith(".pdf"):
            raise ValidationError("output_path must end with .pdf")

        # 2. 描图（自动 posterize/灰度/黑白）
        svg_path = self.trace(
            image_path, mode=mode, path_precision=path_precision, **trace_kwargs
        )

        # 3. 构建 PDF（懒加载依赖）
        try:
            from .print import svg_to_print_pdf

            svg_to_print_pdf(svg_path, output_path, width_mm, height_mm, bleed_mm)
        except ImportError as e:
            raise PrintError(f"缺失印刷依赖: pip install svglib reportlab ({e})") from e
        except Exception as e:
            raise PrintError(f"PDF 构建失败: {e}") from e
        finally:
            if os.path.exists(svg_path):
                os.unlink(svg_path)  # 清理中间 SVG

        return output_path
