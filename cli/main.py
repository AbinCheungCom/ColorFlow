"""
ColorFlow CLI - 命令行矢量描图 / 抠图工具
用法:
  colorflow -i input.png -o output.svg [options]          # 描图（默认命令）
  colorflow trace -i input.png -o output.svg [options]    # 描图（显式子命令）
  colorflow cutout -i input.png -o output.png [options]   # 抠图（透明底 PNG）
  colorflow cutout-trace -i input.png -o output.svg [options]  # 抠图+描图串联
"""

import argparse
import logging
import os
import sys

from colorflow_sdk import ColorFlowSDK
from colorflow_sdk.cutout import CUTOUT_MODELS
from colorflow_sdk.exceptions import ColorFlowError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("colorflow-cli")


def add_trace_args(
    parser: argparse.ArgumentParser,
    include_io: bool = False,
    io_required: bool = True,
) -> None:
    """描图参数（顶层默认命令与 trace / cutout-trace 子命令共用）"""
    if include_io:
        parser.add_argument(
            "-i",
            "--input",
            required=io_required,
            help="输入图片路径（PNG/JPG/WebP/BMP）",
        )
        parser.add_argument(
            "-o", "--output", required=io_required, help="输出 SVG 路径"
        )
    parser.add_argument(
        "-m",
        "--mode",
        default="color",
        choices=["color", "grey", "human"],
        help="描图模式（默认: color）",
    )
    parser.add_argument(
        "--colormode",
        default="rgb8",
        choices=["rgb8", "rgb16", "mono", "grey", "grey16"],
        help="颜色模式（默认: rgb8）",
    )
    parser.add_argument(
        "--hierarchical",
        default="stacked",
        choices=["flat", "stacked"],
        help="输出层级（默认: stacked）",
    )
    parser.add_argument(
        "-f",
        "--filter-speckle",
        type=int,
        default=4,
        metavar="N",
        help="斑点过滤阈值 1-100（默认: 4）",
    )
    parser.add_argument(
        "-p",
        "--color-precision",
        type=int,
        default=6,
        metavar="N",
        help="颜色精度 1-16（默认: 6）",
    )
    parser.add_argument(
        "-l",
        "--layer-difference",
        type=int,
        default=64,
        metavar="N",
        help="图层距离阈值 1-256（默认: 64）",
    )
    parser.add_argument(
        "-c",
        "--corner-threshold",
        type=int,
        default=60,
        metavar="N",
        help="角点阈值 1-180（默认: 60）",
    )
    parser.add_argument(
        "-t",
        "--length-threshold",
        type=float,
        default=2.0,
        metavar="N",
        help="长度阈值 0.1-100（默认: 2.0）",
    )
    parser.add_argument(
        "--path-precision",
        type=int,
        default=7,
        metavar="N",
        help="路径精度 1-16（默认: 7）",
    )


def add_cutout_args(parser: argparse.ArgumentParser) -> None:
    """抠图参数（cutout / cutout-trace 子命令共用）"""
    parser.add_argument(
        "-i", "--input", required=True, help="输入图片路径（PNG/JPG/WebP/BMP）"
    )
    parser.add_argument("-o", "--output", required=True, help="输出路径")
    parser.add_argument(
        "--model",
        default="u2net",
        choices=list(CUTOUT_MODELS),
        help="抠图模型（默认: u2net，轻量可选 silueta；RMBG 系需 --allow-rmbg）",
    )
    parser.add_argument(
        "--allow-rmbg",
        action="store_true",
        help="放行 RMBG 系模型（bria-rmbg 等，BRIA 许可，商用需遵守协议）",
    )
    parser.add_argument(
        "--alpha-matting",
        action="store_true",
        help="启用 alpha matting 边缘细化（毛发场景建议，较慢）",
    )


def run_trace(args) -> None:
    """描图命令"""
    if not os.path.exists(args.input):
        logger.error(f"输入文件不存在: {args.input}")
        sys.exit(1)

    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    sdk = ColorFlowSDK(output_dir=output_dir or "/tmp")
    logger.info(f"开始描图: {args.input} → {args.output} (mode={args.mode})")

    try:
        svg_path = sdk.trace(
            image_path=args.input,
            mode=args.mode,
            colormode=args.colormode,
            hierarchical=args.hierarchical,
            filter_speckle=args.filter_speckle,
            color_precision=args.color_precision,
            layer_difference=args.layer_difference,
            corner_threshold=args.corner_threshold,
            length_threshold=args.length_threshold,
            path_precision=args.path_precision,
        )
    except ColorFlowError as e:
        logger.error(f"✗ 错误: {e}")
        sys.exit(1)

    _move_output(svg_path, args.output, "SVG")


def run_cutout(args) -> None:
    """抠图命令：背景移除 → 透明底 PNG"""
    if not os.path.exists(args.input):
        logger.error(f"输入文件不存在: {args.input}")
        sys.exit(1)

    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    sdk = ColorFlowSDK(output_dir=output_dir or "/tmp")
    logger.info(f"开始抠图: {args.input} → {args.output} (model={args.model})")

    try:
        png_path = sdk.cutout(
            image_path=args.input,
            model=args.model,
            allow_rmbg=args.allow_rmbg,
            alpha_matting=args.alpha_matting,
            output_path=args.output,
        )
    except ColorFlowError as e:
        logger.error(f"✗ 错误: {e}")
        sys.exit(1)

    _move_output(png_path, args.output, "PNG")


def run_cutout_trace(args) -> None:
    """抠图 + 描图串联：背景移除 → 背景色合成 → SVG"""
    if not os.path.exists(args.input):
        logger.error(f"输入文件不存在: {args.input}")
        sys.exit(1)

    try:
        background = tuple(int(v) for v in args.background.split(","))
        if len(background) != 3 or any(not (0 <= v <= 255) for v in background):
            raise ValueError
    except ValueError:
        logger.error("--background 格式应为 R,G,B（0-255），如 255,255,255")
        sys.exit(1)

    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    sdk = ColorFlowSDK(output_dir=output_dir or "/tmp")
    logger.info(
        f"开始抠图+描图串联: {args.input} → {args.output} "
        f"(model={args.model}, background={args.background})"
    )

    try:
        svg_path = sdk.cutout_then_trace(
            image_path=args.input,
            background=background,
            model=args.model,
            allow_rmbg=args.allow_rmbg,
            alpha_matting=args.alpha_matting,
            mode=args.mode,
            colormode=args.colormode,
            hierarchical=args.hierarchical,
            filter_speckle=args.filter_speckle,
            color_precision=args.color_precision,
            layer_difference=args.layer_difference,
            corner_threshold=args.corner_threshold,
            length_threshold=args.length_threshold,
            path_precision=args.path_precision,
        )
    except ColorFlowError as e:
        logger.error(f"✗ 错误: {e}")
        sys.exit(1)

    _move_output(svg_path, args.output, "SVG")


def _move_output(generated_path: str, target_path: str, label: str) -> None:
    """把 SDK 生成的结果复制/移动到目标路径并清理临时文件"""
    import shutil

    if target_path != generated_path:
        try:
            shutil.copy(generated_path, target_path)
        finally:
            if os.path.exists(generated_path):
                os.unlink(generated_path)
        logger.info(f"✓ {label} 已保存至: {target_path}")
    else:
        logger.info(f"✓ {label} 已保存至: {generated_path}")


def main():
    parser = argparse.ArgumentParser(
        prog="colorflow",
        description="ColorFlow CLI - AI 矢量描图 / 抠图工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  colorflow -i input.png -o output.svg
  colorflow trace --input input.png --output output.svg --mode color
  colorflow cutout -i photo.jpg -o photo.png --model silueta
  colorflow cutout -i photo.jpg -o photo.png --alpha-matting
  colorflow cutout-trace -i ai_image.png -o product.svg --background 255,255,255

mode 说明:
  color  - 彩色包装效果图、Logo、插图（默认）
  grey   - 灰度图、线条图、印刷稿
  human  - 人像、人物照片（专项优化）

抠图说明:
  - 默认模型 u2net（176MB，通用高质量）；--model silueta 更轻量（43MB）
  - RMBG 系模型（bria-rmbg / birefnet-rmbg）为 BRIA 许可，需 --allow-rmbg 显式开启
  - 首次运行会联网下载模型权重，可用 U2NET_HOME 指定缓存目录
        """,
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细日志")
    parser.add_argument("--version", action="version", version="ColorFlow CLI v0.3.0")

    # 子命令（缺省为 trace，保持旧用法向后兼容）
    sub = parser.add_subparsers(dest="command")
    parser.set_defaults(command="trace")

    trace_p = sub.add_parser("trace", help="位图 → SVG 描图（默认命令）")
    add_trace_args(trace_p, include_io=True)

    cutout_p = sub.add_parser("cutout", help="抠图：背景移除 → 透明底 PNG")
    add_cutout_args(cutout_p)

    pipe_p = sub.add_parser(
        "cutout-trace", help="一键抠图+描图串联：抠主体 → 背景合成 → SVG"
    )
    add_cutout_args(pipe_p)
    add_trace_args(pipe_p)  # 仅描图参数（-i/-o 已由抠图参数提供）
    pipe_p.add_argument(
        "--background",
        default="255,255,255",
        metavar="R,G,B",
        help="描图前合成背景色（默认: 255,255,255 白底）",
    )

    # 顶层保留描图参数（向后兼容：colorflow -i in.png -o out.svg）
    # 注意：顶层 -i/-o 不能 required=True，否则连子命令一起强制校验；由 main 手动兜底
    add_trace_args(parser, include_io=True, io_required=False)

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.command == "cutout":
        run_cutout(args)
    elif args.command == "cutout-trace":
        run_cutout_trace(args)
    else:
        if not args.input or not args.output:
            parser.error("the following arguments are required: -i/--input, -o/--output")
        run_trace(args)


if __name__ == "__main__":
    main()
