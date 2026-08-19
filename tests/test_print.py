"""export_print 印刷导出测试（依据路线B开发文档 §6）"""

import os

import pikepdf
import pytest

from colorflow_sdk import ColorFlowSDK
from colorflow_sdk.exceptions import ValidationError

SAMPLES = [
    "D:/Abin/ColorFlow/assets/sample.png",
]


def _sample(tmp_path):
    for p in SAMPLES:
        if os.path.exists(p):
            return p
    pytest.skip("sample.png not found")


@pytest.fixture
def sdk(tmp_path):
    return ColorFlowSDK(output_dir=str(tmp_path))


class TestExportPrint:
    def test_export_print_basic(self, sdk, tmp_path):
        out = str(tmp_path / "out.pdf")
        sdk.export_print(_sample(tmp_path), out, 100, 80)
        assert os.path.exists(out)
        with open(out, "rb") as f:
            assert f.read(5) == b"%PDF-"

    def test_export_print_cmyk(self, sdk, tmp_path):
        """真实填充应为 DeviceCMYK；reportlab 初始默认黑(0 0 0 rg)允许"""
        import re

        out = str(tmp_path / "cmyk.pdf")
        sdk.export_print(_sample(tmp_path), out, 100, 80)
        pdf = pikepdf.open(out)
        stream = pdf.pages[0].Contents.read_bytes()
        # 有 CMYK fill 操作符（k）
        assert b" k" in stream, "PDF 内容流缺少 CMYK fill 操作符"
        # 所有 RGB fill 只能是 reportlab 初始默认黑 0 0 0（实际填充必须是 CMYK）
        rg_fills = re.findall(rb"([\d.-]+ [\d.-]+ [\d.-]+) rg", stream)
        non_default = [r for r in rg_fills if r != b"0 0 0"]
        assert non_default == [], f"存在非默认 RGB 填充: {non_default}"

    def test_export_print_dimensions(self, sdk, tmp_path):
        """页面 MediaBox = (width+2·bleed)mm × (height+2·bleed)mm"""
        out = str(tmp_path / "dim.pdf")
        w, h, bleed = 100.0, 80.0, 3.0
        sdk.export_print(_sample(tmp_path), out, w, h, bleed_mm=bleed)
        pdf = pikepdf.open(out)
        mediabox = [float(x) for x in pdf.pages[0].MediaBox]
        # 容差 0.5pt
        assert abs(mediabox[2] - (w + 2 * bleed) / 25.4 * 72) < 0.5
        assert abs(mediabox[3] - (h + 2 * bleed) / 25.4 * 72) < 0.5

    def test_export_print_bleed_box(self, sdk, tmp_path):
        """BleedBox 应内缩 bleed mm"""
        out = str(tmp_path / "bleed.pdf")
        bleed = 3.0
        sdk.export_print(_sample(tmp_path), out, 100, 80, bleed_mm=bleed)
        pdf = pikepdf.open(out)
        page = pdf.pages[0]
        assert "/BleedBox" in page
        bleedbox = [float(x) for x in page.BleedBox]
        bleed_pt = bleed / 25.4 * 72
        assert abs(bleedbox[0] - bleed_pt) < 0.5
        assert abs(bleedbox[1] - bleed_pt) < 0.5

    def test_export_print_grey_mode(self, sdk, tmp_path):
        """grey 模式仍输出 CMYK PDF（非报错）"""
        out = str(tmp_path / "grey.pdf")
        r = sdk.export_print(_sample(tmp_path), out, 100, 80, mode="grey")
        assert os.path.exists(r)

    def test_export_print_invalid(self, sdk, tmp_path):
        src = _sample(tmp_path)
        with pytest.raises(ValidationError):
            sdk.export_print(src, str(tmp_path / "a.pdf"), 0, 80)
        with pytest.raises(ValidationError):
            sdk.export_print(src, str(tmp_path / "a.pdf"), 100, -1)
        with pytest.raises(ValidationError):
            sdk.export_print(src, str(tmp_path / "a.png"), 100, 80)
        with pytest.raises(ValidationError):
            sdk.export_print(src, str(tmp_path / "a.pdf"), 100, 80, bleed_mm=-1)

    def test_export_print_smoke(self, sdk, tmp_path):
        """全流程成功 + 无中间 SVG 残留"""
        out = str(tmp_path / "smoke.pdf")
        r = sdk.export_print(_sample(tmp_path), out, 60, 60)
        assert r == out
        # 无中间 SVG 残留在输出目录
        leftovers = [f for f in os.listdir(tmp_path) if f.endswith(".svg")]
        assert leftovers == []
