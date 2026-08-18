"""vtracer 绑定 mode/colormode 失效补偿测试。

vtracer 0.6.x Python 绑定的 mode/colormode 参数不生效（上游 bug），
SDK 在输入侧预处理实现。这些测试验证灰度/黑白/彩色行为正确。
"""

import re

import pytest

from colorflow_sdk import ColorFlowSDK


def _make_gradient(path):
    """生成一张红→蓝平滑渐变的彩色图（灰度/彩色差异能显现）"""
    from PIL import Image

    w = h = 64
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = (
                int(255 * x / w),
                int(128 * abs(1 - 2 * x / w)),
                int(255 * (1 - x / w)),
            )
    img.save(path)
    return str(path)


def _fills(svg_path):
    data = open(svg_path, encoding="utf-8").read()
    return re.findall(r'fill="#([0-9A-Fa-f]{6})"', data)


class TestModeCompensation:
    def test_color_mode_keeps_color(self, tmp_path):
        sdk = ColorFlowSDK(output_dir=str(tmp_path))
        src = _make_gradient(tmp_path / "g.png")
        svg_path = sdk.trace(src, mode="color", filter_speckle=1)
        fills = _fills(svg_path)
        assert fills, "color 模式应输出颜色"
        non_grey = [f for f in fills if not (f[0:2] == f[2:4] == f[4:6])]
        assert non_grey, "color 模式输出丢失了彩色"

    def test_grey_mode_outputs_grey(self, tmp_path):
        sdk = ColorFlowSDK(output_dir=str(tmp_path))
        src = _make_gradient(tmp_path / "g.png")
        svg_path = sdk.trace(src, mode="grey", filter_speckle=1)
        fills = _fills(svg_path)
        assert fills, "grey 模式应输出颜色"
        for f in fills:
            assert f[0:2] == f[2:4] == f[4:6], f"grey 模式输出非灰度色 #{f}"

    def test_colormode_grey_outputs_grey(self, tmp_path):
        sdk = ColorFlowSDK(output_dir=str(tmp_path))
        src = _make_gradient(tmp_path / "g.png")
        svg_path = sdk.trace(src, mode="color", colormode="grey", filter_speckle=1)
        fills = _fills(svg_path)
        assert fills
        for f in fills:
            assert f[0:2] == f[2:4] == f[4:6], f"colormode=grey 输出非灰度 #{f}"

    def test_colormode_mono_outputs_bw(self, tmp_path):
        sdk = ColorFlowSDK(output_dir=str(tmp_path))
        src = _make_gradient(tmp_path / "g.png")
        svg_path = sdk.trace(src, mode="color", colormode="mono", filter_speckle=1)
        fills = _fills(svg_path)
        assert fills
        for f in fills:
            assert f in ("000000", "FFFFFF"), f"mono 模式输出非纯黑白 #{f}"

    def test_human_mode_falls_back_to_color(self, tmp_path):
        """human 模式无法在输入侧复现，回退为彩色处理（不报错）"""
        sdk = ColorFlowSDK(output_dir=str(tmp_path))
        src = _make_gradient(tmp_path / "g.png")
        svg_path = sdk.trace(src, mode="human", filter_speckle=1)
        assert svg_path.endswith(".svg")
