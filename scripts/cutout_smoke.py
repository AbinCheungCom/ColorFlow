"""CUTOUT 真实模型冒烟测试：生成测试图 → silueta 抠图 → 透明 PNG + 串联 SVG"""
import io
import os
import sys

from PIL import Image

from colorflow_sdk import ColorFlowSDK

OUT = os.path.join(os.path.dirname(__file__), "smoke_out")
os.makedirs(OUT, exist_ok=True)


def make_subject_image(size=(512, 512)):
    """白底 + 居中的彩色圆形主体（四周纯白背景）"""
    img = Image.new("RGB", size, (255, 255, 255))
    # 画一个圆
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    cx, cy = size[0] // 2, size[1] // 2
    r = size[0] // 3
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(200, 40, 40))
    # 加个内圈提高趣味
    draw.ellipse((cx - r // 2, cy - r // 2, cx + r // 2, cy + r // 2), fill=(40, 120, 220))
    return img


def main():
    src = os.path.join(OUT, "input.png")
    make_subject_image().save(src, format="PNG")

    sdk = ColorFlowSDK(output_dir=OUT)

    # 1. 抠图
    print(">> cutout (silueta) ...")
    png = sdk.cutout(src, model="silueta")
    img = Image.open(png)
    print(f"   output: {png} mode={img.mode} size={img.size}")
    # 验证四角透明、中心不透明
    corners = [img.getpixel((0, 0)), img.getpixel((img.width - 1, 0)),
               img.getpixel((0, img.height - 1)), img.getpixel((img.width - 1, img.height - 1))]
    center = img.getpixel((img.width // 2, img.height // 2))
    print(f"   corners alpha: {[c[3] for c in corners]}, center alpha: {center[3]}")
    assert all(c[3] == 0 for c in corners), "四角应全透明"
    assert center[3] > 200, "中心应不透明"
    print("   ✓ 透明底校验通过")

    # 2. 一键抠图+描图
    print(">> cutout_then_trace (silueta) ...")
    svg = sdk.cutout_then_trace(src, model="silueta")
    with open(svg, encoding="utf-8") as f:
        content = f.read()
    print(f"   output: {svg} size={len(content)} bytes")
    assert "<svg" in content
    print("   ✓ SVG 串联通过")

    # 3. 对比：不抠图直接描图（展示路径数量差异）
    print(">> trace without cutout (对照组) ...")
    raw_svg = sdk.trace(src, mode="color")
    with open(raw_svg, encoding="utf-8") as f:
        raw_content = f.read()
    n_raw = raw_content.count("<path")
    n_cut = content.count("<path")
    print(f"   raw paths: {n_raw}, cutout-trace paths: {n_cut}")
    print("   ✓ 串联后路径应更少（背景噪声被移除）")

    print("\nALL SMOKE TESTS PASSED")


if __name__ == "__main__":
    sys.exit(main())
