"""API 集成测试"""

from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

# 测试素材目录
TEST_ASSETS = Path(__file__).parent.parent / "assets"
SAMPLE_PNG = TEST_ASSETS / "sample.png"

TEST_API_KEY = "test-api-key"
MAX_SIZE = 10 * 1024 * 1024  # 与 api.config.COLORFLOW_MAX_FILE_SIZE 默认一致


class TestHealthEndpoint:
    """健康检查端点测试"""

    def test_health_check(self):
        """测试健康检查接口（无需认证）"""
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestRootEndpoint:
    """根路径端点测试"""

    def test_root(self):
        """测试根路径"""
        response = client.get("/")
        assert response.status_code == 200
        assert "service" in response.json()


class TestTraceEndpointAuth:
    """trace 端点认证测试"""

    def test_trace_requires_api_key(self):
        """缺少 API key 应返回 401"""
        response = client.post(
            "/api/v1/trace",
            files={"image": ("a.png", b"fake", "image/png")},
        )
        assert response.status_code == 401

    def test_trace_wrong_api_key(self):
        """错误 API key 应返回 401"""
        response = client.post(
            "/api/v1/trace",
            files={"image": ("a.png", b"fake", "image/png")},
            headers={"x-api-key": "wrong-key"},
        )
        assert response.status_code == 401

    def test_trace_non_ascii_api_key_not_500(self):
        """非 ASCII API key 不应触发 500（此前 compare_digest 会抛 TypeError）。

        注意：TestClient(httpx) 无法发送非 ASCII header（客户端层按 ascii 编码拒绝），
        因此这里用 ASGI scope 直接验证中间件 dispatch 行为——这正是真实 uvicorn
        接收原始 bytes header 的场景。
        """
        import asyncio

        from fastapi import Request
        from fastapi.responses import Response

        from api.middleware.auth import AuthMiddleware

        async def run():
            scope = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "POST",
                "scheme": "http",
                "path": "/api/v1/trace",
                "raw_path": b"/api/v1/trace",
                "query_string": b"",
                "root_path": "",
                "headers": [
                    # 真实 uvicorn 中 header 是原始 bytes（非 ASCII）
                    (b"x-api-key", "中文密钥😀".encode()),
                    (b"host", b"testserver"),
                    (b"content-type", b"multipart/form-data; boundary=test"),
                ],
                "client": ("testclient", 50000),
                "server": ("testserver", 80),
                "state": {},
            }

            async def call_next(request):
                return Response(status_code=200)

            middleware = AuthMiddleware(lambda app: app)
            response = await middleware.dispatch(Request(scope), call_next)
            return response.status_code

        assert asyncio.run(run()) == 401


class TestTraceEndpointValidation:
    """trace 端点参数校验测试"""

    def test_trace_unsupported_content_type(self):
        """不支持的图片类型应返回 415"""
        response = client.post(
            "/api/v1/trace",
            files={"image": ("a.gif", b"GIF89a", "image/gif")},
            headers={"x-api-key": TEST_API_KEY},
        )
        assert response.status_code == 415

    def test_trace_missing_image(self):
        """缺少文件应返回 422"""
        response = client.post(
            "/api/v1/trace",
            headers={"x-api-key": TEST_API_KEY},
        )
        assert response.status_code == 422

    def test_trace_invalid_mode(self, sample_png):
        """非法 mode 应返回 400"""
        if not sample_png:
            import pytest

            pytest.skip("Sample image not found")
        response = client.post(
            "/api/v1/trace",
            data={"mode": "invalid"},
            files={"image": ("sample.png", open(sample_png, "rb"), "image/png")},
            headers={"x-api-key": TEST_API_KEY},
        )
        assert response.status_code == 400

    def test_trace_file_too_large(self):
        """超过大小限制应返回 413"""
        response = client.post(
            "/api/v1/trace",
            files={"image": ("big.png", b"x" * (MAX_SIZE + 1), "image/png")},
            headers={"x-api-key": TEST_API_KEY},
        )
        assert response.status_code == 413


class TestTraceEndpointSuccess:
    """trace 端点成功路径（需要 sample.png + vtracer）"""

    def test_trace_success(self, sample_png):
        """合法图片应返回 200 和 SVG 内容"""
        if not sample_png:
            import pytest

            pytest.skip("Sample image not found")
        with open(sample_png, "rb") as f:
            response = client.post(
                "/api/v1/trace",
                files={"image": ("sample.png", f, "image/png")},
                headers={"x-api-key": TEST_API_KEY},
            )
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/svg+xml"
        assert b"<svg" in response.content


class TestCutoutEndpoint:
    """抠图端点测试"""

    def test_cutout_requires_api_key(self):
        """缺少 API key 应返回 401"""
        response = client.post(
            "/api/v1/cutout",
            files={"image": ("a.png", b"fake", "image/png")},
        )
        assert response.status_code == 401

    def test_cutout_unsupported_type(self):
        """不支持的图片类型应返回 415"""
        response = client.post(
            "/api/v1/cutout",
            files={"image": ("a.gif", b"GIF89a", "image/gif")},
            headers={"x-api-key": TEST_API_KEY},
        )
        assert response.status_code == 415

    def test_cutout_rmbg_blocked(self, sample_png):
        """未授权 RMBG 系模型应返回 400（BRIA 许可红线）"""
        if not sample_png:
            import pytest

            pytest.skip("Sample image not found")
        with open(sample_png, "rb") as f:
            response = client.post(
                "/api/v1/cutout",
                data={"model": "bria-rmbg"},
                files={"image": ("sample.png", f, "image/png")},
                headers={"x-api-key": TEST_API_KEY},
            )
        assert response.status_code == 400
        assert "BRIA" in response.json()["detail"]

    def test_cutout_success(self, sample_png, monkeypatch):
        """合法图片应返回 200 和透明 PNG 内容"""
        import io

        from PIL import Image

        import colorflow_sdk.cutout as cutout_mod

        if not sample_png:
            import pytest

            pytest.skip("Sample image not found")

        def fake_remove(image, **kwargs):
            rgba = image.convert("RGBA")
            rgba.putalpha(200)
            return rgba

        monkeypatch.setattr(cutout_mod, "_run_rembg", fake_remove)

        with open(sample_png, "rb") as f:
            response = client.post(
                "/api/v1/cutout",
                files={"image": ("sample.png", f, "image/png")},
                headers={"x-api-key": TEST_API_KEY},
            )
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        # PNG 魔数
        assert response.content[:8] == b"\x89PNG\r\n\x1a\n"
        img = Image.open(io.BytesIO(response.content))
        assert img.mode == "RGBA"

    def test_cutout_trace_bad_background(self, sample_png):
        """background 格式非法应返回 400"""
        if not sample_png:
            import pytest

            pytest.skip("Sample image not found")
        with open(sample_png, "rb") as f:
            response = client.post(
                "/api/v1/cutout-trace",
                data={"background": "red"},
                files={"image": ("sample.png", f, "image/png")},
                headers={"x-api-key": TEST_API_KEY},
            )
        assert response.status_code == 400

    def test_cutout_trace_success(self, sample_png, monkeypatch):
        """一键串联端点应返回 200 和 SVG 内容"""
        import colorflow_sdk.cutout as cutout_mod

        if not sample_png:
            import pytest

            pytest.skip("Sample image not found")

        def fake_remove(image, **kwargs):
            rgba = image.convert("RGBA")
            rgba.putalpha(200)
            return rgba

        monkeypatch.setattr(cutout_mod, "_run_rembg", fake_remove)

        with open(sample_png, "rb") as f:
            response = client.post(
                "/api/v1/cutout-trace",
                files={"image": ("sample.png", f, "image/png")},
                headers={"x-api-key": TEST_API_KEY},
            )
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/svg+xml"
        assert b"<svg" in response.content
