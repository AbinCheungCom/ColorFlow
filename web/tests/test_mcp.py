"""MCP Server 冒烟测试"""

import json

import pytest

import mcp_server as ms


def test_four_core_tools_registered():
    # FastMCP 2.x 内部结构不直接暴露，通过装饰器后的可调用对象验证工具存在
    assert callable(ms.trace_image)
    assert callable(ms.match_pantone)
    assert callable(ms.quote_print)
    assert callable(ms.trace_and_match)


def test_match_pantone_success():
    data = json.loads(ms.match_pantone("#DA291C"))
    assert data["success"] is True
    assert len(data["matches"]) > 0
    m = data["matches"][0]
    assert "name" in m and "hex" in m and "delta_e" in m


def test_match_pantone_bad_hex():
    data = json.loads(ms.match_pantone("bad"))
    assert data.get("error")


def test_quote_print_fields():
    data = json.loads(ms.quote_print(210, 297, 1000, 4, 120, "offset"))
    assert data["success"] is True
    for key in ("ink_cost_usd", "setup_cost_usd", "total_cost_usd", "cost_per_unit_usd", "breakdown"):
        assert key in data["result"]


def test_trace_image_bad_extension():
    data = json.loads(ms.trace_image("photo.gif"))
    assert data.get("error")


class TestTraceAndMatch:
    def test_bad_extension(self):
        data = json.loads(ms.trace_and_match("photo.gif"))
        assert data.get("error")

    def test_real_image(self):
        png = _find_sample()
        if not png:
            pytest.skip("sample.png not found")
        data = json.loads(ms.trace_and_match("D:/Abin/ColorFlow/assets/sample.png"))
        assert data["success"] is True
        assert data["svg_path"]
        assert data["color_count"] > 0
        assert data["palette"][0]["color"]["hex"]


def _find_sample():
    from pathlib import Path

    p = Path("D:/Abin/ColorFlow/assets/sample.png")
    return str(p) if p.exists() else None