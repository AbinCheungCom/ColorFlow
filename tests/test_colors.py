"""SVG 主色提取测试"""

import pytest

from colorflow_sdk import extract_svg_colors


class TestExtractSvgColors:
    def test_extracts_fills_ordered(self):
        svg = (
            '<svg><path d="M0" fill="#FF6432"/><path d="M1" fill="#FF6432"/>'
            '<path d="M2" fill="#3060C0"/></svg>'
        )
        colors = extract_svg_colors(svg)
        assert colors[0]["hex"] == "#FF6432"
        assert colors[0]["count"] == 2
        assert colors[1]["hex"] == "#3060C0"
        assert colors[1]["count"] == 1
        assert colors[0]["share"] == round(2 / 3, 3)

    def test_accepts_bytes(self):
        svg = b'<svg><path fill="#123456"/></svg>'
        colors = extract_svg_colors(svg)
        assert colors == [{"hex": "#123456", "count": 1, "share": 1.0}]

    def test_top_n_limit(self):
        svg = "".join(
            f'<path fill="#{i:06X}"/>' for i in range(1, 8)
        )
        colors = extract_svg_colors(svg, top_n=3)
        assert len(colors) == 3

    def test_no_fill_returns_empty(self):
        assert extract_svg_colors("<svg><path d='M0'/></svg>") == []

    def test_ignores_non_hex_fill(self):
        svg = '<svg><path fill="url(#grad1)"/><path fill="red"/></svg>'
        assert extract_svg_colors(svg) == []

    def test_invalid_type(self):
        with pytest.raises(TypeError):
            extract_svg_colors(123)

    def test_uppercases_hex(self):
        svg = '<svg><path fill="#ff6432"/></svg>'
        assert extract_svg_colors(svg)[0]["hex"] == "#FF6432"

    def test_normalizes_3_digit_hex(self):
        # 3 位缩写如 #f60 不是合法 6 位 hex，应忽略
        svg = '<svg><path fill="#f60"/><path fill="#FF6432"/></svg>'
        assert extract_svg_colors(svg)[0]["hex"] == "#FF6432"
