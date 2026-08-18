"""ColorFlow MCP Server — 让 AI Agent 直接调用描图 / Pantone 匹配 / 印刷报价能力。

运行方式：
    mcp run mcp_server.py            # 或
    python mcp_server.py

接入 Claude Code（~/.claude.json 或项目 .mcp.json）：
    "mcpServers": { "colorflow": { "command": "python", "args": ["/path/to/mcp_server.py"] } }
"""

import json
import math

from fastmcp import FastMCP

from colorflow_sdk import extract_svg_colors
from mcp_print.tools.colors import (
    _cmyk_to_lab,
    _hex_to_rgb,
    _rgb_to_lab,
    pantone_search,
)
from mcp_print.tools.cost import print_cost_estimate

# 复用 Web 应用中的 SDK 实例（同一份 VTracer 输出目录等）
from app import sdk

mcp = FastMCP("ColorFlow")

# 允许的图片扩展名
ALLOWED_EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp")


def _delta_e(hex_color: str, cmyk) -> float:
    """计算 HEX 与某 CMYK 色之间的 ΔE（CIELAB 欧氏距离近似）"""
    lab_hex = _rgb_to_lab(*_hex_to_rgb(hex_color))
    lab_pantone = _cmyk_to_lab(*cmyk)
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(lab_hex, lab_pantone)))


@mcp.tool()
def trace_image(image_path: str, mode: str = "color") -> str:
    """将位图（PNG/JPG/WebP/BMP）转换为 SVG 矢量图。

    Args:
        image_path: 图片文件路径
        mode: color（彩色）| grey（灰度）| human（人像）
    Returns:
        SVG 文件路径
    """
    if not image_path.lower().endswith(ALLOWED_EXT):
        return json.dumps(
            {"error": f"不支持的文件类型，允许: {', '.join(ALLOWED_EXT)}"},
            ensure_ascii=False,
        )
    svg_path = sdk.trace(image_path, mode=mode)
    return json.dumps({"success": True, "svg_path": svg_path}, ensure_ascii=False)


@mcp.tool()
def match_pantone(hex_color: str) -> str:
    """根据 HEX 颜色匹配最近的 5 个 Pantone 色（含 ΔE 与 CMYK）。

    Args:
        hex_color: HEX 颜色，如 "#DA291C" 或 "DA291C"
    Returns:
        JSON: {success, matches: [{name, hex, cmyk, delta_e}]}
    """
    if not hex_color.startswith("#"):
        hex_color = "#" + hex_color
    if len(hex_color) != 7:
        return json.dumps({"error": "HEX 格式应为 #RRGGBB"}, ensure_ascii=False)

    results = pantone_search(hex_color=hex_color)
    matches = [
        {
            "name": m["name"],
            "hex": m["hex"],
            "cmyk": [m["c"], m["m"], m["y"], m["k"]],
            "delta_e": round(_delta_e(hex_color, (m["c"], m["m"], m["y"], m["k"])), 2),
        }
        for m in results.get("matches", [])[:5]
    ]
    return json.dumps({"success": True, "hex": hex_color, "matches": matches}, ensure_ascii=False)


@mcp.tool()
def quote_print(
    width_mm: float,
    height_mm: float,
    qty: int,
    colors: int = 4,
    gsm: float = 120,
    method: str = "offset",
) -> str:
    """计算印刷报价（油墨 + 版材 + 调机 + 印刷全链路成本）。

    Args:
        width_mm: 成品宽（毫米）
        height_mm: 成品高（毫米）
        qty: 印刷数量
        colors: 颜色数
        gsm: 纸张克重
        method: offset（胶印）| flexo（柔版）| gravure（凹版）| screen（丝网）| digital（数码）
    Returns:
        JSON: {success, result: {ink_cost_usd, setup_cost_usd, total_cost_usd,
               cost_per_unit_usd, currency, breakdown}}
    """
    result = print_cost_estimate(
        width_mm=width_mm,
        height_mm=height_mm,
        quantity=qty,
        num_colors=colors,
        paper_gsm=gsm,
        print_method=method,
    )
    payload = {
        "ink_cost_usd": result["ink_cost"],
        "setup_cost_usd": result["setup_cost"],
        "paper_cost_usd": result["paper_cost"],
        "total_cost_usd": result["total_cost"],
        "cost_per_unit_usd": result["cost_per_unit"],
        "currency": result["currency"],
        "breakdown": result["breakdown"],
    }
    return json.dumps({"success": True, "result": payload}, ensure_ascii=False)


@mcp.tool()
def trace_and_match(image_path: str, mode: str = "color") -> str:
    """一键流水线：位图 → SVG → 提取主色 → 每个主色匹配 Pantone（含 ΔE）。

    Args:
        image_path: 图片文件路径
        mode: color | grey | human
    Returns:
        JSON: {success, svg_path, color_count, palette: [{color, pantone_matches}]}
    """
    if not image_path.lower().endswith(ALLOWED_EXT):
        return json.dumps(
            {"error": f"不支持的文件类型，允许: {', '.join(ALLOWED_EXT)}"},
            ensure_ascii=False,
        )
    try:
        svg_path = sdk.trace(image_path, mode=mode)
    except Exception as e:  # noqa: BLE001
        return json.dumps({"error": f"描图失败: {e}"}, ensure_ascii=False)

    with open(svg_path, "rb") as f:
        svg_bytes = f.read()

    palette = []
    for c in extract_svg_colors(svg_bytes, top_n=5):
        matches = [
            {
                "name": m["name"],
                "hex": m["hex"],
                "cmyk": [m["c"], m["m"], m["y"], m["k"]],
                "delta_e": round(
                    _delta_e(c["hex"], (m["c"], m["m"], m["y"], m["k"])), 2
                ),
            }
            for m in pantone_search(hex_color=c["hex"]).get("matches", [])[:3]
        ]
        palette.append({"color": c, "pantone_matches": matches})

    return json.dumps(
        {
            "success": True,
            "svg_path": svg_path,
            "color_count": len(palette),
            "palette": palette,
        },
        ensure_ascii=False,
    )


if __name__ == "__main__":
    mcp.run()