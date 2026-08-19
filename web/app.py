# ColorFlow Web - AI 矢量描图 + Pantone 色彩管理

from flask import Flask, render_template, request, jsonify, Response
import math
import os
import base64
import secrets
import tempfile

from colorflow_sdk import ColorFlowSDK, extract_svg_colors
from colorflow_sdk.exceptions import CutoutError, ValidationError
from mcp_print.tools.colors import (
    pantone_to_cmyk,
    pantone_search,
    cmyk_to_rgb,
    _hex_to_rgb,
    _rgb_to_lab,
    _cmyk_to_lab,
)
from mcp_print.tools.cost import print_cost_estimate

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB
app.config["UPLOAD_FOLDER"] = "/tmp/colorflow-uploads"

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Initialize SDK
sdk = ColorFlowSDK(output_dir="/tmp/colorflow-output")


# 允许的图片类型
ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp", "image/bmp"}

# API Key 认证：设置 COLORFLOW_API_KEY 后启用（生产环境必须设置）；未设置则开放（适合本地开发）
COLORFLOW_API_KEY = os.getenv("COLORFLOW_API_KEY", "").strip()


@app.before_request
def require_api_key():
    """保护 /api/* 路由：已配置 COLORFLOW_API_KEY 时，请求必须携带正确的 x-api-key 头。"""
    if not COLORFLOW_API_KEY:
        return  # 未配置密钥 → 不启用认证
    if not request.path.startswith("/api/"):
        return  # 页面 / 与静态资源保持公开

    api_key = request.headers.get("x-api-key", "")
    # 转 bytes 后恒定时间比较，避免非 ASCII 头抛 TypeError / 时序攻击
    if not secrets.compare_digest(
        api_key.encode("utf-8"), COLORFLOW_API_KEY.encode("utf-8")
    ):
        return (
            jsonify({"error": "Unauthorized: missing or invalid API key"}),
            401,
        )


def _int_arg(value, default):
    """解析 int 表单/查询参数，非法值返回默认值（不抛异常）"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float_arg(value, default):
    """解析 float 表单/查询参数，非法值返回默认值"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _require_hex(hex_color):
    """校验 HEX 颜色格式（#RRGGBB），非法则返回 None"""
    if not hex_color:
        return None
    if not hex_color.startswith("#"):
        hex_color = "#" + hex_color
    if len(hex_color) != 7:
        return None
    try:
        int(hex_color[1:], 16)
    except ValueError:
        return None
    return hex_color.upper()


def _get_uploaded_image():
    """校验并读取上传图片。

    Returns:
        (image_bytes, image_format) 成功；失败时返回 (None, (error_response, status))。
    """
    if "image" not in request.files:
        return None, (jsonify({"error": "No image provided"}), 400)

    file = request.files["image"]
    if not file.filename:
        return None, (jsonify({"error": "Empty file"}), 400)

    content_type = file.content_type or "image/png"
    if content_type not in ALLOWED_CONTENT_TYPES:
        return None, (
            jsonify({"error": f"Unsupported file type: {content_type}"}),
            415,
        )

    format_map = {
        "image/png": "png",
        "image/jpeg": "jpeg",
        "image/webp": "webp",
        "image/bmp": "bmp",
    }
    return (file.read(), format_map[content_type]), None


def _trace_parameters():
    """从表单读取描图参数（非法数值回退默认值）"""
    return {
        "mode": request.form.get("mode", "color"),
        "filter_speckle": _int_arg(request.form.get("filter_speckle"), 4),
        "color_precision": _int_arg(request.form.get("color_precision"), 6),
        "layer_difference": _int_arg(request.form.get("layer_difference"), 64),
        "corner_threshold": _int_arg(request.form.get("corner_threshold"), 60),
        "path_precision": _int_arg(request.form.get("path_precision"), 7),
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/trace", methods=["POST"])
def trace_image():
    """位图 → SVG 矢量描图"""
    upload, err = _get_uploaded_image()
    if err:
        return err

    image_bytes, image_format = upload
    params = _trace_parameters()

    try:
        svg_bytes = sdk.trace_bytes(
            image_bytes,
            image_format=image_format,
            **params,
        )
        # Return as base64 for easier JS handling
        b64 = base64.b64encode(svg_bytes).decode("utf-8")
        return jsonify(
            {
                "success": True,
                "svg_base64": b64,
                "size": len(svg_bytes),
            }
        )
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/trace/colors", methods=["POST"])
def trace_colors():
    """一键流水线：位图 → SVG → 提取主色 → Pantone 匹配（含 ΔE）"""
    upload, err = _get_uploaded_image()
    if err:
        return err

    image_bytes, image_format = upload
    params = _trace_parameters()

    try:
        svg_bytes = sdk.trace_bytes(
            image_bytes,
            image_format=image_format,
            **params,
        )
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    try:
        # 提取主色并逐一匹配 Pantone
        colors = extract_svg_colors(svg_bytes, top_n=5)
        palette = []
        for c in colors:
            lab_hex = _rgb_to_lab(*_hex_to_rgb(c["hex"]))
            matches = []
            for m in pantone_search(hex_color=c["hex"]).get("matches", [])[:3]:
                lab_pantone = _cmyk_to_lab(m["c"], m["m"], m["y"], m["k"])
                de = math.sqrt(
                    sum((a - b) ** 2 for a, b in zip(lab_hex, lab_pantone))
                )
                _rgb = cmyk_to_rgb(m["c"], m["m"], m["y"], m["k"])
                matches.append(
                    {
                        "name": m["name"],
                        "hex": m["hex"],
                        "cmyk": [m["c"], m["m"], m["y"], m["k"]],
                        "rgb": [_rgb["r"], _rgb["g"], _rgb["b"]],
                        "delta_e": round(de, 2),
                    }
                )
            palette.append(
                {
                    "color": {
                        "hex": c["hex"],
                        "count": c["count"],
                        "share": c["share"],
                        "rgb": list(_hex_to_rgb(c["hex"])),
                    },
                    "pantone_matches": matches,
                }
            )

        return jsonify(
            {
                "success": True,
                "svg_base64": base64.b64encode(svg_bytes).decode("utf-8"),
                "size": len(svg_bytes),
                "palette": palette,
                "color_count": len(palette),
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/pantone/match", methods=["POST"])
def match_pantone():
    """HEX → Pantone 匹配"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400
    hex_color = _require_hex(data.get("hex_color", "").strip())
    if not hex_color:
        return jsonify({"error": "Invalid hex_color. Expected format: #RRGGBB"}), 400

    try:
        results = pantone_search(hex_color=hex_color)
        matches = results.get("matches", [])[:5]

        # Convert input hex to LAB for Delta E calculation
        rgb_hex_tuple = _hex_to_rgb(hex_color)
        lab_hex = _rgb_to_lab(*rgb_hex_tuple)

        # Enrich with delta E and RGB
        enriched = []
        for m in matches:
            c, mm, y, k = m["c"], m["m"], m["y"], m["k"]
            rgb = cmyk_to_rgb(c, mm, y, k)
            # Delta E via LAB
            lab_pantone = _cmyk_to_lab(c, mm, y, k)
            de_value = math.sqrt(
                sum((a - b) ** 2 for a, b in zip(lab_hex, lab_pantone))
            )
            de_interp = (
                "excellent — imperceptible difference"
                if de_value < 1
                else "good — barely perceptible"
                if de_value < 3
                else "fair — noticeable difference"
                if de_value < 6
                else "poor — obvious difference"
            )
            enriched.append(
                {
                    "name": m["name"],
                    "hex": m["hex"],
                    "cmyk": [c, mm, y, k],
                    "rgb": rgb,
                    "delta_e": round(de_value, 2),
                    "interpretation": de_interp,
                }
            )

        return jsonify(
            {
                "success": True,
                "matches": enriched,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/pantone/lookup", methods=["GET"])
def pantone_lookup():
    """Pantone 名称精确查询"""
    name = request.args.get("name", "").strip()
    if not name:
        return jsonify({"error": "No name provided"}), 400

    try:
        result = pantone_to_cmyk(name)
        return jsonify(
            {
                "success": True,
                "result": result,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/pantone/colors", methods=["GET"])
def list_colors():
    """获取所有 Pantone 颜色（分页）"""
    page = _int_arg(request.args.get("page"), 1)
    limit = _int_arg(request.args.get("limit"), 50)
    search = request.args.get("search", "").strip()

    # 分页参数边界约束
    page = max(page, 1)
    limit = min(max(limit, 1), 200)

    try:
        from mcp_print.tools.colors import _load_db

        db = _load_db()

        if search:
            search = search.lower()
            db = [c for c in db if search in c.get("name", "").lower()]

        total = len(db)
        start = (page - 1) * limit
        end = start + limit
        items = db[start:end]

        return jsonify(
            {
                "success": True,
                "items": items,
                "total": total,
                "page": page,
                "limit": limit,
                "pages": (total + limit - 1) // limit,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/cost/quote", methods=["POST"])
def cost_quote():
    """印刷报价"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400
    try:
        result = print_cost_estimate(
            width_mm=float(data.get("width", 210)),
            height_mm=float(data.get("height", 297)),
            quantity=int(data.get("qty", 1000)),
            num_colors=int(data.get("colors", 4)),
            paper_gsm=float(data.get("gsm", 120)),
            print_method=data.get("method", "offset"),
        )
        # 映射为前端期望的 USD 命名字段（mcp-print 返回 ink_cost/total_cost/...，无 _usd 后缀）
        payload = {
            "ink_cost_usd": result["ink_cost"],
            "setup_cost_usd": result["setup_cost"],
            "paper_cost_usd": result["paper_cost"],
            "total_cost_usd": result["total_cost"],
            "cost_per_unit_usd": result["cost_per_unit"],
            "currency": result["currency"],
            "breakdown": result["breakdown"],
        }
        return jsonify(
            {
                "success": True,
                "result": payload,
            }
        )
    except (ValueError, TypeError) as e:
        return jsonify({"error": f"Invalid input: {e}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/print/export", methods=["POST"])
def export_print():
    """位图 → 生产印刷级 CMYK PDF 下载（export_print SDK 前端入口）"""
    upload, err = _get_uploaded_image()
    if err:
        return err

    image_bytes, image_format = upload
    width_mm = _float_arg(request.form.get("width_mm"), 0)
    height_mm = _float_arg(request.form.get("height_mm"), 0)
    bleed_mm = _float_arg(request.form.get("bleed_mm"), 3.0)
    mode = request.form.get("mode", "color")

    if width_mm <= 0 or height_mm <= 0:
        return jsonify({"error": "width_mm / height_mm 必须大于 0"}), 400
    if bleed_mm < 0:
        return jsonify({"error": "bleed_mm 不能为负"}), 400

    tmp_in, pdf_out = None, None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=f".{image_format}", delete=False
        ) as tmp:
            tmp.write(image_bytes)
            tmp_in = tmp.name

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            pdf_out = tmp.name

        sdk.export_print(
            tmp_in,
            pdf_out,
            width_mm=width_mm,
            height_mm=height_mm,
            bleed_mm=bleed_mm,
            mode=mode,
        )
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if tmp_in and os.path.exists(tmp_in):
            os.unlink(tmp_in)

    with open(pdf_out, "rb") as f:
        pdf_bytes = f.read()
    if os.path.exists(pdf_out):
        os.unlink(pdf_out)

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="colorflow_print.pdf"',
        },
    )


def _cutout_form_params():
    """从表单读取抠图参数"""
    return {
        "model": request.form.get("model", "u2net"),
        "allow_rmbg": request.form.get("allow_rmbg", "false").lower() == "true",
        "alpha_matting": request.form.get("alpha_matting", "false").lower() == "true",
    }


@app.route("/api/cutout", methods=["POST"])
def cutout_image():
    """抠图：背景移除 → 透明底 PNG（base64 JSON，前端预览 + 下载）"""
    upload, err = _get_uploaded_image()
    if err:
        return err

    image_bytes, _ = upload
    params = _cutout_form_params()

    try:
        png_bytes = sdk.cutout_bytes(image_bytes, **params)
        b64 = base64.b64encode(png_bytes).decode("utf-8")
        return jsonify(
            {
                "success": True,
                "png_base64": b64,
                "size": len(png_bytes),
            }
        )
    except (ValidationError, CutoutError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/cutout/trace", methods=["POST"])
def cutout_trace():
    """一键「抠图 + 描图」串联：抠主体 → 背景色合成 → SVG（base64 JSON）"""
    upload, err = _get_uploaded_image()
    if err:
        return err

    image_bytes, _ = upload
    params = _cutout_form_params()
    try:
        bg = tuple(int(v) for v in request.form.get("background", "255,255,255").split(","))
        if len(bg) != 3 or any(not (0 <= v <= 255) for v in bg):
            raise ValueError
        params["background"] = bg
    except ValueError:
        return jsonify({"error": "background 格式应为 R,G,B（0-255），如 255,255,255"}), 400

    try:
        svg_bytes = sdk.cutout_then_trace_bytes(image_bytes, **params)
        b64 = base64.b64encode(svg_bytes).decode("utf-8")
        return jsonify(
            {
                "success": True,
                "svg_base64": b64,
                "size": len(svg_bytes),
            }
        )
    except (ValidationError, CutoutError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )
