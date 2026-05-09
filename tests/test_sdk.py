"""SDK 单元测试"""
import os
import pytest
from pathlib import Path

from colorflow_sdk import ColorFlowSDK
from colorflow_sdk.exceptions import ValidationError, TraceError


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
            with open(svg_path, "r") as f:
                content = f.read()
            assert "<svg" in content
            assert len(content) > 100
