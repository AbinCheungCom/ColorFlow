"""ColorFlow Web 集成测试"""

import io
from pathlib import Path

import pytest

import app as app_module
from app import app

client = app.test_client()

# 测试素材（Monorepo：复用仓库根目录 ColorFlow SDK 的 sample.png）
_SAMPLE_PATHS = [
    Path(__file__).resolve().parent.parent.parent / "assets" / "sample.png",
    Path("/d/Abin/ColorFlow/assets/sample.png"),
]


def _sample_png():
    for p in _SAMPLE_PATHS:
        if p.exists():
            return p
    return None


class TestIndex:
    def test_homepage(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"ColorFlow" in resp.data


class TestTrace:
    def test_no_image(self):
        resp = client.post("/api/trace", data={})
        assert resp.status_code == 400

    def test_empty_filename(self):
        resp = client.post(
            "/api/trace",
            data={"image": (io.BytesIO(b"x"), "")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_unsupported_content_type(self):
        resp = client.post(
            "/api/trace",
            data={"image": (io.BytesIO(b"GIF89a"), "a.gif")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 415

    def test_invalid_mode(self):
        resp = client.post(
            "/api/trace",
            data={
                "image": (io.BytesIO(b"fake"), "a.png"),
                "mode": "invalid-mode",
            },
            content_type="multipart/form-data",
        )
        # 非法 mode：SDK ValidationError 应映射为 400
        assert resp.status_code == 400

    def test_invalid_numeric_param_falls_back(self):
        """非法数字参数应回退默认值而不 500"""
        png = _sample_png()
        if not png:
            pytest.skip("sample.png not found")
        with open(png, "rb") as f:
            resp = client.post(
                "/api/trace",
                data={
                    "image": (f, "sample.png"),
                    "filter_speckle": "not-a-number",
                    "mode": "color",
                },
                content_type="multipart/form-data",
            )
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_success_trace(self):
        png = _sample_png()
        if not png:
            pytest.skip("sample.png not found")
        with open(png, "rb") as f:
            resp = client.post(
                "/api/trace",
                data={"image": (f, "sample.png")},
                content_type="multipart/form-data",
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["svg_base64"]
        assert data["size"] > 0


class TestPantoneMatch:
    def test_no_json_content_type(self):
        # 未带 application/json -> Flask 自动 415
        resp = client.post("/api/pantone/match")
        assert resp.status_code == 415

    def test_empty_json_body(self):
        # 带 JSON content-type 但 body 为空 -> 400
        resp = client.post("/api/pantone/match", data="", content_type="application/json")
        assert resp.status_code == 400

    def test_no_hex(self):
        resp = client.post("/api/pantone/match", json={})
        assert resp.status_code == 400

    def test_invalid_hex(self):
        resp = client.post("/api/pantone/match", json={"hex_color": "xyz"})
        assert resp.status_code == 400

    def test_valid_hex(self):
        resp = client.post("/api/pantone/match", json={"hex_color": "#DA291C"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert len(data["matches"]) > 0
        m = data["matches"][0]
        # 前端依赖的字段
        assert "name" in m and "hex" in m and "cmyk" in m and "delta_e" in m


class TestPantoneLookup:
    def test_missing_name(self):
        resp = client.get("/api/pantone/lookup")
        assert resp.status_code == 400

    def test_lookup_success(self):
        resp = client.get("/api/pantone/lookup?name=485C")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["result"]["name"]


class TestPantoneColors:
    def test_list_default(self):
        resp = client.get("/api/pantone/colors")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["total"] > 0
        assert len(data["items"]) <= 50

    def test_invalid_page_falls_back(self):
        resp = client.get("/api/pantone/colors?page=abc&limit=xyz")
        assert resp.status_code == 200  # 回退默认值而不是 500
        data = resp.get_json()
        assert data["page"] == 1

    def test_search(self):
        resp = client.get("/api/pantone/colors?search=red&limit=10")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert all("red" in c.get("name", "").lower() for c in data["items"])


class TestApiAuth:
    """API Key 认证测试（默认未配置 → 开放；配置后保护 /api/*）"""

    def test_disabled_by_default(self):
        assert app_module.COLORFLOW_API_KEY == ""

    def test_requires_key_when_configured(self, monkeypatch):
        monkeypatch.setattr(app_module, "COLORFLOW_API_KEY", "test-secret-key")
        # 无 key → 401
        r = client.get("/api/pantone/colors")
        assert r.status_code == 401
        # 错误 key → 401
        r = client.get("/api/pantone/colors", headers={"x-api-key": "wrong"})
        assert r.status_code == 401
        # 正确 key → 200
        r = client.get("/api/pantone/colors", headers={"x-api-key": "test-secret-key"})
        assert r.status_code == 200
        # 非 ASCII key → 401（不应 500）
        r = client.get("/api/pantone/colors", headers={"x-api-key": "中文😀"})
        assert r.status_code == 401

    def test_static_and_index_open_when_configured(self, monkeypatch):
        monkeypatch.setattr(app_module, "COLORFLOW_API_KEY", "test-secret-key")
        # 页面 / 与静态资源不受保护
        assert client.get("/").status_code == 200
        assert client.get("/static/app.js").status_code == 200


class TestTraceColors:
    """一键流水线：描图 → 主色 → Pantone 匹配"""

    def test_no_image(self):
        resp = client.post("/api/trace/colors", data={})
        assert resp.status_code == 400

    def test_unsupported_type(self):
        resp = client.post(
            "/api/trace/colors",
            data={"image": (io.BytesIO(b"GIF89a"), "a.gif")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 415

    def test_pipeline_success(self):
        png = _sample_png()
        if not png:
            pytest.skip("sample.png not found")
        with open(png, "rb") as f:
            resp = client.post(
                "/api/trace/colors",
                data={"image": (f, "sample.png")},
                content_type="multipart/form-data",
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["svg_base64"]
        assert data["color_count"] > 0
        assert len(data["palette"]) == data["color_count"]
        item = data["palette"][0]
        # 主色与 Pantone 匹配字段
        assert "color" in item and "hex" in item["color"]
        assert "pantone_matches" in item
        if item["pantone_matches"]:
            m = item["pantone_matches"][0]
            assert "name" in m and "hex" in m and "delta_e" in m

    def test_pipeline_color_has_rgb(self):
        """潘通色卡：主色应含 RGB 值（需求：色卡展示 RGB）"""
        png = _sample_png()
        if not png:
            pytest.skip("sample.png not found")
        with open(png, "rb") as f:
            resp = client.post(
                "/api/trace/colors",
                data={"image": (f, "sample.png")},
                content_type="multipart/form-data",
            )
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["color_count"] > 0
        for item in data["palette"]:
            rgb = item["color"].get("rgb")
            assert rgb and len(rgb) == 3
            assert all(isinstance(v, int) and 0 <= v <= 255 for v in rgb)

    def test_pipeline_matches_have_rgb(self):
        """潘通色卡：匹配色应含 RGB 值"""
        png = _sample_png()
        if not png:
            pytest.skip("sample.png not found")
        with open(png, "rb") as f:
            resp = client.post(
                "/api/trace/colors",
                data={"image": (f, "sample.png")},
                content_type="multipart/form-data",
            )
        data = resp.get_json()
        assert resp.status_code == 200
        for item in data["palette"]:
            for m in item["pantone_matches"]:
                rgb = m.get("rgb")
                assert rgb and len(rgb) == 3

    def test_pipeline_backward_compat(self):
        """向后兼容：现有字段(hex/count/share/name/cmyk/delta_e)全部保留"""
        png = _sample_png()
        if not png:
            pytest.skip("sample.png not found")
        with open(png, "rb") as f:
            resp = client.post(
                "/api/trace/colors",
                data={"image": (f, "sample.png")},
                content_type="multipart/form-data",
            )
        data = resp.get_json()
        assert resp.status_code == 200
        for item in data["palette"]:
            assert {"hex", "count", "share"} <= set(item["color"].keys())
            for m in item["pantone_matches"]:
                assert {"name", "hex", "cmyk", "delta_e"} <= set(m.keys())


class TestPrintExport:
    """印刷 PDF 导出端点（export_print M3）"""

    def test_no_image(self):
        resp = client.post("/api/print/export", data={})
        assert resp.status_code == 400

    def test_missing_dimensions(self):
        png = _sample_png()
        if not png:
            pytest.skip("sample.png not found")
        with open(png, "rb") as f:
            resp = client.post(
                "/api/print/export",
                data={"image": (f, "sample.png")},
                content_type="multipart/form-data",
            )
        assert resp.status_code == 400

    def test_invalid_dimensions(self):
        png = _sample_png()
        if not png:
            pytest.skip("sample.png not found")
        with open(png, "rb") as f:
            resp = client.post(
                "/api/print/export",
                data={"image": (f, "sample.png"), "width_mm": "0", "height_mm": "80"},
                content_type="multipart/form-data",
            )
        assert resp.status_code == 400

    def test_success_pdf(self):
        png = _sample_png()
        if not png:
            pytest.skip("sample.png not found")
        with open(png, "rb") as f:
            resp = client.post(
                "/api/print/export",
                data={
                    "image": (f, "sample.png"),
                    "width_mm": "100",
                    "height_mm": "80",
                    "bleed_mm": "3",
                },
                content_type="multipart/form-data",
            )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.data[:5] == b"%PDF-"


class TestCutout:
    """抠图端点（rembg 默认未装时以 mock 覆盖 _run_rembg 测试流程）"""

    def test_no_image(self):
        resp = client.post("/api/cutout", data={})
        assert resp.status_code == 400

    def test_unsupported_type(self):
        resp = client.post(
            "/api/cutout",
            data={"image": (io.BytesIO(b"GIF89a"), "a.gif")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 415

    def test_rmbg_blocked_without_allow(self, monkeypatch):
        """未授权 RMBG 模型应 400（BRIA 许可红线，无需真实模型）"""
        png = _sample_png()
        if not png:
            pytest.skip("sample.png not found")
        with open(png, "rb") as f:
            resp = client.post(
                "/api/cutout",
                data={"image": (f, "sample.png"), "model": "bria-rmbg"},
                content_type="multipart/form-data",
            )
        assert resp.status_code == 400
        assert "BRIA" in resp.get_json()["error"]

    def test_success_cutout(self, monkeypatch):
        """合法图片 + mock rembg → 透明 PNG base64"""
        import colorflow_sdk.cutout as cutout_mod
        from PIL import Image

        png = _sample_png()
        if not png:
            pytest.skip("sample.png not found")

        def fake_remove(image, **kwargs):
            rgba = image.convert("RGBA")
            rgba.putalpha(200)
            return rgba

        monkeypatch.setattr(cutout_mod, "_run_rembg", fake_remove)

        with open(png, "rb") as f:
            resp = client.post(
                "/api/cutout",
                data={"image": (f, "sample.png"), "model": "silueta"},
                content_type="multipart/form-data",
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["png_base64"]
        img = Image.open(io.BytesIO(__import__("base64").b64decode(data["png_base64"])))
        assert img.mode == "RGBA"

    def test_success_cutout_trace(self, monkeypatch):
        """一键串联：mock rembg + 真实 VTracer → SVG base64"""
        import colorflow_sdk.cutout as cutout_mod

        png = _sample_png()
        if not png:
            pytest.skip("sample.png not found")

        def fake_remove(image, **kwargs):
            rgba = image.convert("RGBA")
            rgba.putalpha(200)
            return rgba

        monkeypatch.setattr(cutout_mod, "_run_rembg", fake_remove)

        with open(png, "rb") as f:
            resp = client.post(
                "/api/cutout/trace",
                data={"image": (f, "sample.png"), "background": "255,255,255"},
                content_type="multipart/form-data",
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["svg_base64"]
        assert b"<svg" in __import__("base64").b64decode(data["svg_base64"])


class TestCostQuote:
    def test_no_json_content_type(self):
        resp = client.post("/api/cost/quote")
        assert resp.status_code == 415

    def test_empty_json_body(self):
        resp = client.post("/api/cost/quote", data="", content_type="application/json")
        assert resp.status_code == 400

    def test_invalid_numbers(self):
        resp = client.post(
            "/api/cost/quote",
            json={"width": "abc", "height": "def", "qty": "xyz"},
        )
        # float('abc') 抛 ValueError -> 400
        assert resp.status_code == 400

    def test_success_and_field_mapping(self):
        """回归：前端期望的 _usd 字段必须存在（此前全部显示 N/A）"""
        resp = client.post(
            "/api/cost/quote",
            json={"width": 210, "height": 297, "qty": 1000, "colors": 4, "gsm": 120, "method": "offset"},
        )
        assert resp.status_code == 200
        r = resp.get_json()["result"]
        for key in ("ink_cost_usd", "setup_cost_usd", "paper_cost_usd", "total_cost_usd", "cost_per_unit_usd", "currency", "breakdown"):
            assert key in r, f"missing key: {key}"
        assert r["breakdown"]["plates"] is not None
        assert r["total_cost_usd"] > 0
