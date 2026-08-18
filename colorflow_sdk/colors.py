"""SVG 颜色提取工具：从 VTracer 输出中提取填充主色"""

import re
from collections import Counter

_FILL_RE = re.compile(r'fill="([^"]+)"')
_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def extract_svg_colors(svg_bytes, top_n: int = 5) -> list[dict]:
    """
    从 SVG 中提取填充色，按出现频率降序返回。

    Args:
        svg_bytes: SVG 内容（bytes 或 str）
        top_n: 返回出现最多的前 N 个颜色

    Returns:
        [{"hex": "#RRGGBB", "count": int, "share": float}, ...]
        无可识别颜色时返回空列表。

    Raises:
        TypeError: svg_bytes 不是 bytes/str
    """
    if not isinstance(svg_bytes, (bytes, str)):
        raise TypeError("svg_bytes must be bytes or str")

    text = (
        svg_bytes.decode("utf-8", errors="ignore")
        if isinstance(svg_bytes, bytes)
        else svg_bytes
    )

    fills = _FILL_RE.findall(text)
    hexes = [f.upper() for f in fills if _HEX_RE.match(f)]
    if not hexes:
        return []

    counter = Counter(hexes)
    total = len(hexes)
    return [
        {"hex": h, "count": c, "share": round(c / total, 3)}
        for h, c in counter.most_common(top_n)
    ]
