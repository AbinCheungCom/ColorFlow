"""pytest fixtures"""
import os
import pytest
from pathlib import Path

# 测试素材目录
TEST_ASSETS = Path(__file__).parent.parent / "assets"


@pytest.fixture
def sample_png():
    """返回测试用 PNG 图片路径"""
    path = TEST_ASSETS / "sample.png"
    if not path.exists():
        pytest.skip(f"Sample image not found: {path}")
    return str(path)


@pytest.fixture
def output_dir(tmp_path):
    """返回临时输出目录"""
    return str(tmp_path)


@pytest.fixture
def sdk(output_dir):
    """返回配置好的 SDK 实例"""
    from colorflow_sdk import ColorFlowSDK
    return ColorFlowSDK(output_dir=output_dir)
