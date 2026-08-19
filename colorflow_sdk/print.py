"""ColorFlow 印刷导出：位图 → 生产印刷级 CMYK PDF

依据《路线B_export_print开发文档.md》实现。
svglib 解析 SVG → reportlab 图形树；RGB → CMYK 后由 reportlab 输出
/DeviceCMYK 的 PDF（含出血与 BleedBox）。
"""

from reportlab.graphics import renderPDF, shapes
from reportlab.lib.colors import CMYKColor, Color
from reportlab.pdfgen import canvas
from svglib.svglib import svg2rlg

MM_PER_PT = 25.4 / 72.0  # 1pt = 1/72 inch


def rgb_to_cmyk_color(color: Color) -> CMYKColor:
    """reportlab Color(0-1 RGB) → CMYKColor。用 PIL 做标准 ICC 近似转换。"""
    from PIL import Image

    r, g, b = (int(c * 255) for c in (color.red, color.green, color.blue))
    cmyk = Image.new("RGB", (1, 1), (r, g, b)).convert("CMYK").load()[0, 0]
    # PIL CMYK 为 0-255 制 → 归一化到 0-1
    return CMYKColor(cmyk[0] / 255, cmyk[1] / 255, cmyk[2] / 255, cmyk[3] / 255)


def replace_fill_colors(obj):
    """递归把 reportlab 图形树所有 fill/stroke 颜色从 RGB 换成 CMYK。"""
    if isinstance(obj, (shapes.Drawing, shapes.Group)):
        for child in obj.getContents():
            replace_fill_colors(child)
    else:
        for attr in ("fillColor", "strokeColor"):
            color = getattr(obj, attr, None)
            if isinstance(color, Color) and not isinstance(color, CMYKColor):
                setattr(obj, attr, rgb_to_cmyk_color(color))
    return obj


def svg_to_print_pdf(svg_path: str, pdf_path: str, width_mm: float,
                     height_mm: float, bleed_mm: float) -> str:
    """SVG → CMYK PDF（成品尺寸 + 出血 + BleedBox）。

    Args:
        svg_path: VTracer 输出的 SVG 路径
        pdf_path: 输出 PDF 路径
        width_mm / height_mm: 成品尺寸（毫米）
        bleed_mm: 出血（毫米）

    Returns:
        pdf_path

    Raises:
        ValueError: SVG 尺寸非法
    """
    drawing = svg2rlg(svg_path)          # SVG → reportlab Drawing（pt 单位）
    replace_fill_colors(drawing)         # RGB → CMYK

    src_w, src_h = drawing.width, drawing.height  # 源像素（1px = 1pt @72dpi）
    if src_w <= 0 or src_h <= 0:
        raise ValueError("SVG 尺寸非法")

    # 页面尺寸 = 成品 + 2×出血（mm → pt）
    page_w = (width_mm + 2 * bleed_mm) / MM_PER_PT
    page_h = (height_mm + 2 * bleed_mm) / MM_PER_PT

    # 缩放：源宽(pt) → 目标成品宽(pt)
    scale = (width_mm / MM_PER_PT) / src_w
    drawing.scale(scale, scale)

    c = canvas.Canvas(pdf_path, pagesize=(page_w, page_h))
    bleed_pt = bleed_mm / MM_PER_PT
    renderPDF.draw(drawing, c, bleed_pt, bleed_pt)
    # 页面盒子（印刷标记）
    c.setCropBox((0, 0, page_w, page_h))
    c.setBleedBox((bleed_pt, bleed_pt, page_w - bleed_pt, page_h - bleed_pt))
    c.save()
    return pdf_path
