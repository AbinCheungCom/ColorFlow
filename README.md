# ColorFlow

> AI Agent 矢量描图 SDK — 位图（PNG/JPG/WebP/BMP）高质量转换为 SVG + 抠图（背景移除）

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)

## 定位

ColorFlow 是一个 **AI Native 矢量描图封装层**，核心能力是将位图高质量转换为 SVG，并提供 CUTOUT 抠图模块（背景移除 → 透明底 PNG）。专注执行层，不做意图理解、不做参数决策——供 AI Agent（外部智能体）调用。

**一句话**：VTracer 是一个可被 AI Agent 调用的高质量矢量描图引擎，rembg 是抠图内核，ColorFlow 为两者封装三种调用接口。

## 仓库结构（Monorepo）

```
ColorFlow/
├── colorflow_sdk/       # Python SDK（描图 / 抠图 / 潘通 / 印刷导出）
├── api/                 # FastAPI 服务（/api/v1/trace /cutout /cutout-trace）
├── cli/                 # CLI（colorflow trace / cutout / cutout-trace）
├── web/                 # ColorFlow Web 前端（Flask 单页 + MCP Server）
├── docker/              # Docker 镜像（CLI 轻量版 / API 版）
├── tests/               # SDK 测试
└── scripts/             # 冒烟测试脚本
```

Web 前端（`web/`）通过 editable 本地引用根目录 SDK（`pip install -e ..`），无需单独发布即可使用全部能力。

## 三种调用方式

### 1. Python SDK（推荐）

```bash
pip install colorflow-sdk
```

```python
from colorflow_sdk import ColorFlowSDK

sdk = ColorFlowSDK(output_dir="/tmp")

# 基本调用
svg_path = sdk.trace("input.png")

# 完整参数
svg_path = sdk.trace(
    "input.png",
    mode="color",
    filter_speckle=4,
    layer_difference=64,
    corner_threshold=60,
    path_precision=7,
)

# 内存模式（不落盘）
svg_bytes = sdk.trace_bytes(image_bytes, image_format="png")

# 降级重试（mode 失败时按 color -> grey -> human 顺序自动降级）
svg_path = sdk.trace_with_retry("input.png", mode="color", max_retries=3)

# 提取 SVG 主色（供配色 / Pantone 匹配等下游使用）
from colorflow_sdk import extract_svg_colors

with open(svg_path, "rb") as f:
    colors = extract_svg_colors(f.read(), top_n=5)
# [{"hex": "#FF6432", "count": 2, "share": 0.5}, ...] 按出现频率降序
```

### 1.1 CUTOUT 抠图（背景移除）

```bash
pip install "colorflow-sdk[cutout]"   # 安装 rembg 内核
```

```python
# 抠图：带背景图片 → 透明底 PNG
png_path = sdk.cutout("photo_with_bg.png")               # 默认 u2net 模型
png_path = sdk.cutout("photo.png", model="silueta")      # 轻量模型（43MB）
png_path = sdk.cutout("hair.png", model="birefnet-general", alpha_matting=True)

# 内存模式
png_bytes = sdk.cutout_bytes(image_bytes)

# 一键「抠图 + 描图」串联：抠主体 → 白底合成 → SVG
# （VTracer 忽略 alpha，透明像素会变黑，必须先合成背景；默认白底贴合印刷）
svg_path = sdk.cutout_then_trace("ai_image.png")
svg_bytes = sdk.cutout_then_trace_bytes(image_bytes, background=(255, 255, 255))
```

**模型与许可**：

| 模型 | 体积 | 说明 | 许可 |
|------|------|------|------|
| `u2net`（默认） | 176MB | 通用高质量 | ✅ 可商用 |
| `silueta` | 43MB | 轻量快速 | ✅ 可商用 |
| `isnet` | 176MB | 边缘更优 | ✅ 可商用 |
| `birefnet-general` / `birefnet-2k` | 重 | BiRefNet SOTA，毛发/半透明边缘最佳 | ✅ 可商用 |
| `bria-rmbg` / `birefnet-rmbg` | — | ⚠️ BRIA 许可，需 `allow_rmbg=True` | ⚠️ 商用需遵守协议 |

> **授权红线**：RMBG 系模型权重为 BRIA 许可（每月 100 万张内免费，需遵守协议），
> SDK / API / CLI 默认拒绝，必须显式传入 `allow_rmbg=True` / `--allow-rmbg` 才会放行。
> 首次运行会联网下载模型权重（`~/.u2net`，可用环境变量 `U2NET_HOME` 指定缓存目录）。

### 2. HTTP API

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

> **注意**：`COLORFLOW_API_KEY` 为**必需**环境变量，未设置时服务拒绝启动。

```bash
export COLORFLOW_API_KEY="your-api-key"

curl -X POST http://localhost:8000/api/v1/trace \
  -H "X-API-KEY: $COLORFLOW_API_KEY" \
  -F "image=@input.png" \
  -F "mode=color" \
  -F "filter_speckle=4" \
  -o output.svg

# 抠图（返回透明底 PNG）
curl -X POST http://localhost:8000/api/v1/cutout \
  -H "X-API-KEY: $COLORFLOW_API_KEY" \
  -F "image=@photo.png" \
  -F "model=silueta" \
  -o output.png

# 一键抠图 + 描图（返回 SVG）
curl -X POST http://localhost:8000/api/v1/cutout-trace \
  -H "X-API-KEY: $COLORFLOW_API_KEY" \
  -F "image=@ai_image.png" \
  -F "background=255,255,255" \
  -o output.svg
```

访问文档：http://localhost:8000/docs（生产环境可通过 `COLORFLOW_ENABLE_DOCS=false` 关闭）

### 3. CLI

```bash
pip install "colorflow-sdk[cutout]"
colorflow --input input.png --output output.svg --mode color   # 描图（默认命令）
colorflow trace --input input.png --output output.svg          # 描图（显式子命令）
colorflow cutout -i photo.jpg -o photo.png --model silueta     # 抠图 → 透明底 PNG
colorflow cutout -i photo.jpg -o photo.png --alpha-matting     # 边缘细化
colorflow cutout-trace -i ai.png -o product.svg                # 一键抠图+描图
```

或使用 Docker：

```bash
docker run --rm -v $(pwd):/data colorflow \
  --input /data/input.png \
  --output /data/output.svg
```

> Docker CLI 镜像保持轻量（未内置 rembg），抠图命令请使用 `pip install "colorflow-sdk[cutout]"` 或 API 镜像。

## 核心参数

| 参数 | 默认值 | 可选值 | 说明 |
|------|--------|--------|------|
| mode | color | color/grey/human | 描图模式 |
| colormode | rgb8 | rgb8/rgb16/mono/grey/grey16 | 颜色模式 |
| hierarchical | stacked | flat/stacked | 输出层级 |
| filter_speckle | 4 | 1-100 | 斑点过滤 |
| color_precision | 6 | 1-16 | 颜色精度 |
| layer_difference | 64 | 1-256 | 图层距离阈值 |
| corner_threshold | 60 | 1-180 | 角点阈值 |
| length_threshold | 2.0 | 0.1-100 | 长度阈值 |
| path_precision | 7 | 1-16 | 路径精度 |

## mode 适用场景

| mode | 适用场景 |
|------|---------|
| color | 彩色包装效果图、Logo、插图 |
| grey | 灰度图、线条图、印刷稿 |
| human | 人像、人物照片（专项优化）|

## 安装

```bash
# SDK only
pip install colorflow-sdk

# With API server
pip install "colorflow-sdk[api]"
uvicorn api.main:app --reload

# With cutout (抠图)
pip install "colorflow-sdk[cutout]"

# Development
git clone https://github.com/Abinius/ColorFlow.git
cd ColorFlow
pip install -e ".[dev,cutout]"
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `COLORFLOW_API_KEY` | **（必需，无默认值）** | API 访问密钥，缺失时服务拒绝启动 |
| `COLORFLOW_OUTPUT_DIR` | `/tmp` | SDK 输出目录 |
| `COLORFLOW_MAX_FILE_SIZE` | `10485760`（10MB） | 上传文件大小上限（字节）|
| `COLORFLOW_ALLOWED_ORIGINS` | `*` | CORS 允许来源（逗号分隔）|
| `COLORFLOW_ENABLE_DOCS` | `true` | 是否暴露 `/docs` `/redoc` 交互文档 |
| `U2NET_HOME` | `~/.u2net` | rembg 模型权重缓存目录（首次运行联网下载）|

## 错误码

| 错误码 | 类型 | 说明 |
|--------|------|------|
| 400 | 参数错误 | 检查输入参数是否合法（含 RMBG 模型未授权） |
| 401 | 认证失败 | 缺少或错误的 API KEY |
| 413 | 文件过大 | 超过 `COLORFLOW_MAX_FILE_SIZE` 限制 |
| 415 | 类型不支持 | 仅支持 PNG/JPEG/WebP/BMP |
| 422 | 参数校验失败 | FastAPI 表单参数不合法 |
| 500 | 执行失败 | VTracer / rembg 执行失败，可重试 |

## License

MIT © AbinCheungCom

## 相关项目

| 项目 | 说明 |
|------|------|
| [ColorFlow Web](https://github.com/Abinius/ColorFlow-Web) | ColorFlow Web 前端（矢量描图 + Pantone 色彩管理 + 印刷报价）|
