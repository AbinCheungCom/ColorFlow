# ColorFlow Web - AI 矢量描图 + Pantone 色彩管理

from flask import Flask, render_template, request, jsonify
import math
import os
import base64

from colorflow_sdk import ColorFlowSDK
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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/trace", methods=["POST"])
def trace_image():
    """位图 → SVG 矢量描图"""
    if "image" not in request.files:
        return jsonify({"error": "No image provided"}), 400

    file = request.files["image"]
    if not file.filename:
        return jsonify({"error": "Empty file"}), 400

    # Read image bytes
    image_bytes = file.read()

    # Get parameters
    mode = request.form.get("mode", "color")
    filter_speckle = int(request.form.get("filter_speckle", 4))
    color_precision = int(request.form.get("color_precision", 6))
    layer_difference = int(request.form.get("layer_difference", 64))
    corner_threshold = int(request.form.get("corner_threshold", 60))
    path_precision = int(request.form.get("path_precision", 7))

    try:
        # Infer image format from content-type
        content_type = file.content_type or "image/png"
        content_type_map = {
            "image/png": "png",
            "image/jpeg": "jpeg",
            "image/webp": "webp",
            "image/bmp": "bmp",
        }
        image_format = content_type_map.get(content_type, "png")

        svg_bytes = sdk.trace_bytes(
            image_bytes,
            image_format=image_format,
            mode=mode,
            filter_speckle=filter_speckle,
            color_precision=color_precision,
            layer_difference=layer_difference,
            corner_threshold=corner_threshold,
            path_precision=path_precision,
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
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/pantone/match", methods=["POST"])
def match_pantone():
    """HEX → Pantone 匹配"""
    data = request.get_json()
    hex_color = data.get("hex_color", "").strip()
    if not hex_color:
        return jsonify({"error": "No hex_color provided"}), 400

    if not hex_color.startswith("#"):
        hex_color = "#" + hex_color

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
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 50))
    search = request.args.get("search", "").strip()

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
    try:
        result = print_cost_estimate(
            width_mm=float(data.get("width", 210)),
            height_mm=float(data.get("height", 297)),
            quantity=int(data.get("qty", 1000)),
            num_colors=int(data.get("colors", 4)),
            paper_gsm=float(data.get("gsm", 120)),
            print_method=data.get("method", "offset"),
        )
        return jsonify(
            {
                "success": True,
                "result": result,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    import os

    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )
