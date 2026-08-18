"""SDK 单元测试"""

import os

import pytest

from colorflow_sdk import ColorFlowSDK
from colorflow_sdk.exceptions import TraceError, ValidationError


class TestColorFlowSDK:
    """SDK 测试用例"""

    def test_init_default(self):
        """测试默认初始化"""
        sdk = ColorFlowSDK()
        assert sdk.output_dir == "/tmp"

    def test_init_custom_dir(self, output_dir):
        """测试自定义输出目录"""
        sdk = ColorFlowSDK(output_dir=output_dir)
        assert sdk.output_dir == output_dir

    def test_validate_mode_valid(self, sdk):
        """测试合法的 mode"""
        sdk._validate_mode("color")
        sdk._validate_mode("grey")
        sdk._validate_mode("human")

    def test_validate_mode_invalid(self, sdk):
        """测试非法的 mode"""
        with pytest.raises(ValidationError):
            sdk._validate_mode("invalid")

    def test_validate_colormode_valid(self, sdk):
        """测试合法的 colormode"""
        sdk._validate_colormode("rgb8")
        sdk._validate_colormode("mono")

    def test_validate_range_valid(self, sdk):
        """测试合法的范围校验"""
        sdk._validate_range("filter_speckle", 4, 1, 100)
        sdk._validate_range("filter_speckle", 1, 1, 100)
        sdk._validate_range("filter_speckle", 100, 1, 100)

    def test_validate_range_invalid(self, sdk):
        """测试超出范围的校验"""
        with pytest.raises(ValidationError):
            sdk._validate_range("filter_speckle", 0, 1, 100)
        with pytest.raises(ValidationError):
            sdk._validate_range("filter_speckle", 101, 1, 100)

    def test_validate_float_range(self, sdk):
        """测试浮点数范围校验"""
        sdk._validate_float_range("length_threshold", 2.0, 0.1, 100.0)
        sdk._validate_float_range("length_threshold", 0.1, 0.1, 100.0)

    def test_validate_float_range_invalid(self, sdk):
        """测试浮点数范围校验失败"""
        with pytest.raises(ValidationError):
            sdk._validate_float_range("length_threshold", 0.0, 0.1, 100.0)

    def test_trace_invalid_path(self, sdk):
        """测试无效路径"""
        with pytest.raises(ValidationError):
            sdk.trace("/nonexistent/path/image.png")

    def test_trace_path_traversal(self, sdk):
        """测试路径遍历攻击防护"""
        with pytest.raises(ValidationError):
            sdk.trace("../etc/passwd")

    def test_get_version(self):
        """测试版本获取"""
        version = ColorFlowSDK.get_version()
        assert version is not None
        assert isinstance(version, str)


class TestTraceWithRetry:
    """trace_with_retry 降级重试测试"""

    def test_downgrades_on_trace_error(self, sdk, monkeypatch):
        """mode 失败时应按 color -> grey -> human 顺序降级"""
        calls = []

        def fake_trace(image_path, mode="color", **kwargs):
            calls.append(mode)
            if mode == "color":
                raise TraceError("simulated color failure")
            return "/tmp/fake.svg"

        monkeypatch.setattr(sdk, "trace", fake_trace)
        result = sdk.trace_with_retry("img.png", mode="color", max_retries=3)

        assert result == "/tmp/fake.svg"
        assert calls == ["color", "grey"]  # color 失败后降级到 grey 成功

    def test_exhausts_all_modes(self, sdk, monkeypatch):
        """所有 mode 都失败时应抛出 TraceError"""
        calls = []

        def fake_trace(image_path, mode="color", **kwargs):
            calls.append(mode)
            raise TraceError("always fails")

        monkeypatch.setattr(sdk, "trace", fake_trace)
        with pytest.raises(TraceError):
            sdk.trace_with_retry("img.png", mode="color", max_retries=3)

        assert calls == ["color", "grey", "human"]

    def test_start_from_non_first_mode(self, sdk, monkeypatch):
        """初始 mode 不是 color 时，应从该 mode 开始并按序降级"""
        calls = []

        def fake_trace(image_path, mode="color", **kwargs):
            calls.append(mode)
            if mode == "grey":
                raise TraceError("grey fails")
            return "/tmp/fake.svg"

        monkeypatch.setattr(sdk, "trace", fake_trace)
        result = sdk.trace_with_retry("img.png", mode="grey", max_retries=3)

        assert result == "/tmp/fake.svg"
        assert calls == ["grey", "human"]  # grey 失败 -> human 成功，不回到 color

    def test_validation_error_not_retried(self, sdk, monkeypatch):
        """参数校验错误（ValidationError）不应重试"""
        def fake_trace(image_path, mode="color", **kwargs):
            raise ValidationError("bad param")

        monkeypatch.setattr(sdk, "trace", fake_trace)
        with pytest.raises(ValidationError):
            sdk.trace_with_retry("img.png", mode="color", max_retries=3)

    def test_max_retries_capped_by_modes(self, sdk, monkeypatch):
        """重试次数不应超出剩余可用 mode 数量"""
        calls = []

        def fake_trace(image_path, mode="color", **kwargs):
            calls.append(mode)
            raise TraceError("always fails")

        monkeypatch.setattr(sdk, "trace", fake_trace)
        with pytest.raises(TraceError):
            # max_retries=10 但只有 color/grey/human 三个可用模式
            sdk.trace_with_retry("img.png", mode="color", max_retries=10)

        assert len(calls) == 3


class TestTraceIntegration:
    """描图集成测试（需要 sample.png）"""

    def test_trace_with_retry_all_modes(self, sample_png, output_dir):
        """测试三种模式的降级重试"""
        sdk = ColorFlowSDK(output_dir=output_dir)

        # 依次测试每种模式
        for mode in ["color", "grey", "human"]:
            svg_path = sdk.trace(sample_png, mode=mode)
            assert os.path.exists(svg_path)
            assert svg_path.endswith(".svg")

            # 验证 SVG 内容
            with open(svg_path) as f:
                content = f.read()
            assert "<svg" in content
            assert len(content) > 100
