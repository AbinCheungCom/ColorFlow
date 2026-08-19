"""CUTOUT 抠图模块测试"""

import io
import os

import pytest
from PIL import Image

import colorflow_sdk.cutout as cutout_mod
from colorflow_sdk import ColorFlowSDK
from colorflow_sdk.exceptions import CutoutError, ValidationError


def _make_image(path, size=(64, 48), color=(200, 30, 30)):
    """生成纯色测试图"""
    img = Image.new("RGB", size, color)
    img.save(path, format="PNG")
    return str(path)


def _fake_remove(image, **kwargs):
    """模拟 rembg 输出：中心区域不透明、四周边框透明"""
    rgba = image.convert("RGBA")
    w, h = rgba.size
    out = Image.new("RGBA", rgba.size)
    for y in range(h):
        for x in range(w):
            r, g, b = rgba.getpixel((x, y))[:3]
            if x < w // 4 or x >= 3 * w // 4 or y < h // 4 or y >= 3 * h // 4:
                out.putpixel((x, y), (r, g, b, 0))
            else:
                out.putpixel((x, y), (r, g, b, 255))
    return out


class TestCutoutValidation:
    """参数校验与许可红线"""

    def test_invalid_model(self, sdk):
        """未知模型应报 ValidationError"""
        with pytest.raises(ValidationError):
            sdk.cutout("x.png", model="nonexistent-model")

    def test_validate_model_direct(self):
        """validate_model 合法模型不抛异常"""
        for model in cutout_mod.CUTOUT_MODELS:
            cutout_mod.validate_model(model)
        cutout_mod.validate_model("bria-rmbg", allow_rmbg=True)

    def test_rmbg_blocked_without_allow(self, sdk):
        """RMBG 系模型未显式授权应拒绝并提示 BRIA 许可"""
        with pytest.raises(ValidationError) as exc_info:
            sdk.cutout("x.png", model="bria-rmbg")
        assert "BRIA" in str(exc_info.value)

    def test_rmbg_allowed_proceeds_to_rembg(self, sdk, tmp_path, monkeypatch):
        """allow_rmbg=True 时通过校验并进入 rembg 调用"""
        src = _make_image(str(tmp_path / "in.png"))
        calls = []

        def fake(image, **kwargs):
            calls.append(kwargs["model_name"])
            return image.convert("RGBA")

        monkeypatch.setattr(cutout_mod, "_run_rembg", fake)
        sdk.cutout(src, model="bria-rmbg", allow_rmbg=True)
        assert calls == ["bria-rmbg"]

    def test_invalid_path(self, sdk):
        """不存在的输入路径应报 ValidationError"""
        with pytest.raises(ValidationError):
            sdk.cutout("/nonexistent/path/image.png")

    def test_output_must_be_png(self, sdk, tmp_path, monkeypatch):
        """输出路径必须 .png 后缀"""
        src = _make_image(str(tmp_path / "in.png"))
        monkeypatch.setattr(
            cutout_mod, "_run_rembg", lambda img, **kw: img.convert("RGBA")
        )
        with pytest.raises(ValidationError):
            sdk.cutout(src, output_path=str(tmp_path / "out.jpg"))

    def test_cutout_bytes_rejects_non_bytes(self, sdk):
        """非 bytes 输入应报 ValidationError"""
        with pytest.raises(ValidationError):
            sdk.cutout_bytes("not bytes")  # type: ignore[arg-type]


class TestCutoutWithMock:
    """mock rembg 后的抠图流程测试"""

    def test_cutout_creates_transparent_png(self, sdk, tmp_path, monkeypatch):
        """抠图产物应为透明底 PNG：四角透明、中心不透明"""
        src = _make_image(str(tmp_path / "in.png"))
        monkeypatch.setattr(cutout_mod, "_run_rembg", _fake_remove)

        out = sdk.cutout(src)

        assert os.path.exists(out)
        assert out.endswith(".png")
        img = Image.open(out)
        assert img.mode == "RGBA"
        assert img.getpixel((0, 0))[3] == 0
        assert img.getpixel((img.width // 2, img.height // 2))[3] == 255

    def test_cutout_respects_output_path(self, sdk, tmp_path, monkeypatch):
        """指定 output_path 时应写入该路径（自动建目录）"""
        src = _make_image(str(tmp_path / "in.png"))
        monkeypatch.setattr(cutout_mod, "_run_rembg", _fake_remove)
        out = str(tmp_path / "sub" / "result.png")

        result = sdk.cutout(src, output_path=out)

        assert result == out
        assert os.path.exists(out)

    def test_cutout_bytes_returns_png(self, sdk, monkeypatch):
        """内存模式返回透明底 PNG 字节"""
        buf = io.BytesIO()
        Image.new("RGB", (32, 32), (10, 200, 100)).save(buf, format="PNG")
        monkeypatch.setattr(cutout_mod, "_run_rembg", _fake_remove)

        out_bytes = sdk.cutout_bytes(buf.getvalue())

        assert isinstance(out_bytes, bytes)
        img = Image.open(io.BytesIO(out_bytes))
        assert img.mode == "RGBA"

    def test_cutout_then_trace(self, sdk, tmp_path, monkeypatch):
        """一键串联：抠图 → 白底合成 → VTracer 描图产出 SVG"""
        src = _make_image(str(tmp_path / "in.png"), size=(128, 128))
        monkeypatch.setattr(cutout_mod, "_run_rembg", _fake_remove)

        svg_path = sdk.cutout_then_trace(src)

        assert os.path.exists(svg_path)
        assert svg_path.endswith(".svg")
        with open(svg_path) as f:
            assert "<svg" in f.read()

    def test_cutout_then_trace_custom_background(self, sdk, tmp_path, monkeypatch):
        """自定义背景色合成后描图"""
        src = _make_image(str(tmp_path / "in.png"), size=(96, 96))
        monkeypatch.setattr(cutout_mod, "_run_rembg", _fake_remove)

        svg_path = sdk.cutout_then_trace(src, background=(255, 0, 0))

        assert os.path.exists(svg_path)

    def test_cutout_then_trace_bytes(self, sdk, monkeypatch):
        """串联内存模式返回 SVG 字节"""
        buf = io.BytesIO()
        Image.new("RGB", (64, 64), (200, 30, 30)).save(buf, format="PNG")
        monkeypatch.setattr(cutout_mod, "_run_rembg", _fake_remove)

        svg_bytes = sdk.cutout_then_trace_bytes(buf.getvalue())

        assert isinstance(svg_bytes, bytes)
        assert b"<svg" in svg_bytes


class TestCutoutIntegration:
    """真实模型集成测试（需联网下载模型权重，默认跳过）

    运行: COLORFLOW_TEST_CUTOUT=1 pytest tests/test_cutout.py -k Integration
    """

    def test_real_cutout_silueta(self, sdk, tmp_path):
        if not os.getenv("COLORFLOW_TEST_CUTOUT"):
            pytest.skip("COLORFLOW_TEST_CUTOUT 未设置，跳过真实模型测试")
        src = _make_image(str(tmp_path / "in.png"), size=(128, 128))
        out = sdk.cutout(src, model="silueta")
        assert os.path.exists(out)
        img = Image.open(out)
        assert img.mode == "RGBA"
