# ColorFlow Web

> AI 矢量描图 + Pantone 色彩管理 + 抠图 — 一个页面搞定从位图到印刷落地

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 定位

ColorFlow Web 是 **ColorFlow 矢量描图 SDK** 和 **Pantone 色彩管理** 的 Web 前端界面，开源可免费部署。将 AI 生成图片的矢量描图、抠图（背景移除）、Pantone 色号匹配、Delta E 色彩偏差计算、印刷报价五大能力聚合在一个页面中。

> 本目录是 ColorFlow Monorepo 的 `web/` 子项目，SDK 为仓库根目录包（editable 本地引用）。

## 五大功能

| 功能 | 说明 |
|------|------|
| **矢量描图** | 上传位图（PNG/JPG/WebP/BMP），VTracer 转 SVG，预览 + 下载 |
| **抠图** | rembg 内核（u2net/silueta 等），背景移除 → 透明底 PNG；一键「抠图 + 描图」串联出 SVG |
| **Pantone 查色** | 输入 Pantone 色号，一键获取 HEX / CMYK / RGB 值 |
| **色彩匹配** | 输入 HEX，自动匹配最近的 5 个 Pantone 色 + ΔE 色彩偏差 |
| **印刷报价** | 尺寸/颜色/纸张/数量 → 全链路油墨+版材+调机+印刷成本 |
| **一键流水线** | 描图后自动提取主色 → 逐一匹配 Pantone → 一键填入报价 |
| **AI Agent 接入** | 内置 MCP Server，Claude Code 等 Agent 可直接调用全部能力 |

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | 原生 HTML + CSS + JS（零框架依赖）|
| 后端 | Flask + Python 3.10+ |
| 描图引擎 | [VTracer](https://github.com/visioncortex/vtracer) (Rust) |
| 抠图引擎 | [rembg](https://github.com/danielgatis/rembg) (u2net/silueta/isnet/BiRefNet) |
| 色彩数据库 | [mcp-print](https://github.com/kcgdz/mcp-print) (2415 Pantone 色) |
| 矢量输出 | [ColorFlow SDK](https://github.com/Abinius/ColorFlow) |

## 工作流

```
上传位图 → 抠图（可选）→ VTracer 描图 → SVG 输出
        └→ 一键主色提取 → Pantone 匹配（ΔE）→ 自动填入报价
```

## 快速启动

### 前提（Monorepo）

```bash
# 在仓库根目录统一安装（SDK + API + cutout + Web 全量）
pip install -e ".[dev,cutout,api]"
pip install -r web/requirements.txt   # web/requirements.txt 已含 `-e ..` 本地 SDK 引用
```

或只装 Web 依赖：

```bash
pip install -r web/requirements.txt   # 从仓库根目录执行，自动 editable 安装根目录 SDK
```

### 运行

```bash
python3 app.py
# → http://localhost:5000
```

### 生产部署

```bash
# 生产环境务必设置 API Key（设置后 /api/* 需要 x-api-key 头，否则开放）
export COLORFLOW_API_KEY="your-secret-key"
export FLASK_DEBUG=false
export PORT=5000
python3 app.py
```

或使用 Gunicorn：

```bash
pip install gunicorn
gunicorn -w 2 -b 0.0.0.0:5000 app:app
```

## AI Agent 接入（MCP Server）

内置 MCP Server，让 Claude Code / Cursor 等 Agent 直接调用描图、Pantone 匹配、报价能力。

```bash
pip install fastmcp
mcp run mcp_server.py
```

接入 Claude Code（`~/.claude.json` 或项目 `.mcp.json`）：

```json
{
  "mcpServers": {
    "colorflow": {
      "command": "python",
      "args": ["/path/to/mcp_server.py"]
    }
  }
}
```

可用工具：

| Tool | 说明 |
|------|------|
| `trace_image` | 位图 → SVG，返回文件路径 |
| `cutout_image` | 抠图：背景移除 → 透明底 PNG |
| `cutout_and_trace` | 一键「抠图 + 描图」串联 → SVG |
| `match_pantone` | HEX → 最近 5 个 Pantone 色 + ΔE |
| `quote_print` | 印刷全链路报价 |
| `export_print` | 位图 → 生产印刷级 CMYK PDF |
| `trace_and_match` | 一键流水线：描图 → 主色 → Pantone 匹配 |

```bash
# Agent 可直接说：
# 「把 D:/img.png 先抠图，再描成矢量，提取主色，匹配 Pantone，报 5000 张 4 色的价格」
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/trace` | 位图 → SVG（multipart/form-data）|
| `POST` | `/api/trace/colors` | 描图 + 主色提取 + Pantone 匹配（一键流水线）|
| `POST` | `/api/cutout` | 抠图：背景移除 → 透明底 PNG（base64）|
| `POST` | `/api/cutout/trace` | 一键抠图 + 描图串联 → SVG（base64）|
| `POST` | `/api/pantone/match` | HEX → Pantone 最近匹配 + ΔE |
| `GET` | `/api/pantone/lookup?name=` | Pantone 色号精确查询 |
| `GET` | `/api/pantone/colors?page=&limit=&search=` | Pantone 颜色列表（分页）|
| `POST` | `/api/cost/quote` | 印刷报价计算 |
| `POST` | `/api/print/export` | 位图 → 生产印刷级 CMYK PDF 下载 |

### 示例

```bash
# 抠图（返回透明 PNG base64；RMBG 系模型需 allow_rmbg=true 遵守 BRIA 许可）
curl -X POST http://localhost:5000/api/cutout \
  -F "image=@photo.png" \
  -F "model=silueta"

# 一键抠图 + 描图（返回 SVG base64）
curl -X POST http://localhost:5000/api/cutout/trace \
  -F "image=@ai_image.png" \
  -F "background=255,255,255"

# 色彩匹配
curl -X POST http://localhost:5000/api/pantone/match \
  -H "Content-Type: application/json" \
  -d '{"hex_color": "#DA291C"}'

# 印刷报价（返回字段带 _usd 后缀 + breakdown 明细）
curl -X POST http://localhost:5000/api/cost/quote \
  -H "Content-Type: application/json" \
  -d '{"width": 210, "height": 297, "qty": 5000, "colors": 4, "gsm": 120, "method": "offset"}'

# 返回示例（部分字段）
# {
#   "success": true,
#   "result": {
#     "ink_cost_usd": 14.05, "setup_cost_usd": 240.0,
#     "total_cost_usd": 259.08, "cost_per_unit_usd": 0.0518,
#     "currency": "USD",
#     "breakdown": {"ink": 14.05, "plates": 140.0, "makeready": 100.0, "run_cost": 5.03, "paper": 0.0}
#   }
# }
```

## 错误码

| 错误码 | 说明 |
|--------|------|
| 400 | 参数错误 / 缺少必要字段 / 非法 JSON |
| 415 | 不支持的图片类型或未带 JSON Content-Type |
| 500 | 服务端执行失败 |

## 配色方案

深色主题（`#0f1117` 背景），主色 Indigo `#6366f1`，强调色 Amber `#f59e0b`，Inter 字体。

## 架构

```
web/（ColorFlow Monorepo 子项目）
├── app.py              # Flask 入口，所有 API 路由（含 /api/cutout 抠图）
├── mcp_server.py       # MCP Server（描图/抠图/潘通/报价/生产导出）
├── templates/
│   └── index.html     # 单页 HTML（5 Tab：描图/抠图/查色/匹配/报价）
├── static/
│   ├── style.css      # 深色主题样式
│   └── app.js         # 前端交互逻辑
└── tests/
    ├── test_app.py    # API 集成测试
    └── test_mcp.py    # MCP Server 冒烟测试
```

## 测试

```bash
pip install pytest
python -m pytest tests/ -q     # 34 个用例
```

## 相关项目

| 项目 | 说明 |
|------|------|
| [ColorFlow SDK](https://github.com/Abinius/ColorFlow) | AI Agent 矢量描图 SDK（Python/CLI/API）|
| [mcp-print](https://github.com/kcgdz/mcp-print) | Pantone + CMYK + Delta E + 印刷报价（2415 色）|
| [vtracer](https://github.com/visioncortex/vtracer) | Rust 矢量描图引擎 |

## License

MIT © AbinCheungCom
