"""
ColorFlow CLI - 命令行矢量描图工具
用法: colorflow --input input.png --output output.svg [options]
"""

import argparse
import logging
import os
import sys

from colorflow_sdk import ColorFlowSDK
from colorflow_sdk.exceptions import ColorFlowError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("colorflow-cli")


def main():
    parser = argparse.ArgumentParser(
        prog="colorflow",
        description="ColorFlow CLI - AI 矢量描图工具（位图 → SVG）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  colorflow -i input.png -o output.svg
  colorflow --input input.png --output output.svg --mode color
  colorflow -i photo.jpg -o result.svg --mode human --filter-speckle 8
  colorflow -i logo.png -o logo.svg --path-precision 10

mode 说明:
  color  - 彩色包装效果图、Logo、插图（默认）
  grey   - 灰度图、线条图、印刷稿
  human  - 人像、人物照片（专项优化）
        """,
    )

    # 必需参数
    parser.add_argument(
        "-i", "--input", required=True, help="输入图片路径（PNG/JPG/WebP/BMP）"
    )
    parser.add_argument("-o", "--output", required=True, help="输出 SVG 路径")

    # 描图参数
    mode_group = parser.add_argument_group("描图参数（可选）")
    mode_group.add_argument(
        "-m",
        "--mode",
        default="color",
        choices=["color", "grey", "human"],
        help="描图模式（默认: color）",
    )
    mode_group.add_argument(
        "--colormode",
        default="rgb8",
        choices=["rgb8", "rgb16", "mono", "grey", "grey16"],
        help="颜色模式（默认: rgb8）",
    )
    mode_group.add_argument(
        "--hierarchical",
        default="stacked",
        choices=["flat", "stacked"],
        help="输出层级（默认: stacked）",
    )
    mode_group.add_argument(
        "-f",
        "--filter-speckle",
        type=int,
        default=4,
        metavar="N",
        help="斑点过滤阈值 1-100（默认: 4）",
    )
    mode_group.add_argument(
        "-p",
        "--color-precision",
        type=int,
        default=6,
        metavar="N",
        help="颜色精度 1-16（默认: 6）",
    )
    mode_group.add_argument(
        "-l",
        "--layer-difference",
        type=int,
        default=64,
        metavar="N",
        help="图层距离阈值 1-256（默认: 64）",
    )
    mode_group.add_argument(
        "-c",
        "--corner-threshold",
        type=int,
        default=60,
        metavar="N",
        help="角点阈值 1-180（默认: 60）",
    )
    mode_group.add_argument(
        "-t",
        "--length-threshold",
        type=float,
        default=2.0,
        metavar="N",
        help="长度阈值 0.1-100（默认: 2.0）",
    )
    mode_group.add_argument(
        "--path-precision",
        type=int,
        default=7,
        metavar="N",
        help="路径精度 1-16（默认: 7）",
    )

    # 其他选项
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细日志")
    parser.add_argument("--version", action="version", version="ColorFlow CLI v0.1.0")

    args = parser.parse_args()

    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # 参数校验
    if not os.path.exists(args.input):
        logger.error(f"输入文件不存在: {args.input}")
        sys.exit(1)

    if args.filter_speckle < 1 or args.filter_speckle > 100:
        logger.error("--filter-speckle 必须在 1-100 范围内")
        sys.exit(1)

    if args.color_precision < 1 or args.color_precision > 16:
        logger.error("--color-precision 必须在 1-16 范围内")
        sys.exit(1)

    # 确保输出目录存在
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # 调用 SDK
    logger.info(f"开始转换: {args.input}")
    logger.info(f"输出路径: {args.output}")
    logger.info(f"描图模式: {args.mode}")

    sdk = ColorFlowSDK(output_dir=output_dir or "/tmp")

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

        # 如果指定了输出路径，复制过去
        if args.output != svg_path:
            import shutil

            shutil.copy(svg_path, args.output)
            os.unlink(svg_path)
            logger.info(f"✓ SVG 已保存至: {args.output}")
        else:
            logger.info(f"✓ SVG 已保存至: {svg_path}")

    except ColorFlowError as e:
        logger.error(f"✗ 错误: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"✗ 未知错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
