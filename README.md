# ColorFlow

> AI Agent 矢量描图 SDK — 位图（PNG/JPG/WebP）高质量转换为 SVG

[![PyPI Version](https://img.shields.io/pypi/v/colorflow-sdk)](https://pypi.org/project/colorflow-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 定位

ColorFlow 是一个 **AI Native 矢量描图封装层**，核心能力是将位图高质量转换为 SVG。专注执行层，不做意图理解、不做参数决策——供 AI Agent（外部智能体）调用。

**一句话**：VTracer 是一个可被 AI Agent 调用的高质量矢量描图引擎，ColorFlow 为其封装三种调用接口。

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
```

### 2. HTTP API

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

```bash
curl -X POST http://localhost:8000/api/v1/trace \
  -H "X-API-KEY: mv-p4ss-k3y-2026" \
  -F "image=@input.png" \
  -F "mode=color" \
  -F "filter_speckle=4" \
  -o output.svg
```

访问文档：http://localhost:8000/docs

### 3. CLI

```bash
pip install colorflow-sdk
colorflow --input input.png --output output.svg --mode color
```

或使用 Docker：

```bash
docker run --rm -v $(pwd):/data colorflow \
  --input /data/input.png \
  --output /data/output.svg
```

## 核心参数

| 参数 | 默认值 | 可选值 | 说明 |
|------|--------|--------|------|
| mode | color | color/grey/human | 描图模式 |
| colormode | rgb8 | rgb8/rgb16/mono/grey/grey16 | 颜色模式 |
| filter_speckle | 4 | 1-100 | 斑点过滤 |
| layer_difference | 64 | 1-256 | 图层距离阈值 |
| corner_threshold | 60 | 1-180 | 角点阈值 |
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

# Development
git clone https://github.com/AbinCheungCom/ColorFlow.git
cd ColorFlow
pip install -e ".[dev]"
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `COLORFLOW_API_KEY` | `mv-p4ss-k3y-2026` | API 访问密钥 |
| `COLORFLOW_OUTPUT_DIR` | `/tmp` | SDK 输出目录 |
| `COLORFLOW_TIMEOUT` | `30` | 请求超时（秒）|

## 错误码

| 错误码 | 类型 | 说明 |
|--------|------|------|
| 400 | 参数错误 | 检查输入参数是否合法 |
| 401 | 认证失败 | 检查 API KEY 是否正确 |
| 404 | 文件不存在 | 检查文件路径 |
| 500 | 执行失败 | VTracer 执行失败，重试 |
| 503 | 服务过载 | 排队重试 |

## License

MIT © AbinCheungCom

## 相关项目

| 项目 | 说明 |
|------|------|
| [ColorFlow Web](https://github.com/AbinCheungCom/ColorFlow-Web) | ColorFlow Web 前端（矢量描图 + Pantone 色彩管理 + 印刷报价）|
