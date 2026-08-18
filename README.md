# ColorFlow Web

> AI 矢量描图 + Pantone 色彩管理 — 一个页面搞定从位图到印刷落地

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 定位

ColorFlow Web 是 **ColorFlow 矢量描图 SDK** 和 **Pantone 色彩管理** 的 Web 前端界面，开源可免费部署。将 AI 生成图片的矢量描图、Pantone 色号匹配、Delta E 色彩偏差计算、印刷报价四大能力聚合在一个页面中。

## 四大功能

| 功能 | 说明 |
|------|------|
| **矢量描图** | 上传位图（PNG/JPG/WebP/BMP），VTracer 转 SVG，预览 + 下载 |
| **Pantone 查色** | 输入 Pantone 色号，一键获取 HEX / CMYK / RGB 值 |
| **色彩匹配** | 输入 HEX，自动匹配最近的 5 个 Pantone 色 + ΔE 色彩偏差 |
| **印刷报价** | 尺寸/颜色/纸张/数量 → 全链路油墨+版材+调机+印刷成本 |

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | 原生 HTML + CSS + JS（零框架依赖）|
| 后端 | Flask + Python 3.10+ |
| 描图引擎 | [VTracer](https://github.com/visioncortex/vtracer) (Rust) |
| 色彩数据库 | [mcp-print](https://github.com/kcgdz/mcp-print) (2415 Pantone 色) |
| 矢量输出 | [ColorFlow SDK](https://github.com/Abinius/ColorFlow) |

## 工作流

```
上传位图 → VTracer 描图 → SVG 输出
                          ↓
              HEX 填色值 → Pantone 匹配 → ΔE 偏差
                                        ↓
                              印刷报价 → 全链路成本
```

## 快速启动

### 前提

```bash
pip install -r requirements.txt
```

> 注意：`colorflow-sdk` 未发布到 PyPI，需从 GitHub 安装（requirements.txt 已内置 `git+` 引用）。若想装本地开发版：

```bash
pip install -e /path/to/ColorFlow     # ColorFlow SDK 仓库本地路径
```

### 运行

```bash
python3 app.py
# → http://localhost:5000
```

### 生产部署

```bash
export FLASK_DEBUG=false
export PORT=5000
python3 app.py
```

或使用 Gunicorn：

```bash
pip install gunicorn
gunicorn -w 2 -b 0.0.0.0:5000 app:app
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/trace` | 位图 → SVG（multipart/form-data）|
| `POST` | `/api/pantone/match` | HEX → Pantone 最近匹配 + ΔE |
| `GET` | `/api/pantone/lookup?name=` | Pantone 色号精确查询 |
| `GET` | `/api/pantone/colors?page=&limit=&search=` | Pantone 颜色列表（分页）|
| `POST` | `/api/cost/quote` | 印刷报价计算 |

### 示例

```bash
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
colorflow-web/
├── app.py              # Flask 入口，所有 API 路由
├── templates/
│   └── index.html     # 单页 HTML（4 Tab）
├── static/
│   ├── style.css      # 深色主题样式
│   └── app.js         # 前端交互逻辑
└── tests/
    └── test_app.py    # 集成测试（21 个用例）
```

## 测试

```bash
pip install pytest
python -m pytest tests/ -q
```

## 相关项目

| 项目 | 说明 |
|------|------|
| [ColorFlow SDK](https://github.com/Abinius/ColorFlow) | AI Agent 矢量描图 SDK（Python/CLI/API）|
| [mcp-print](https://github.com/kcgdz/mcp-print) | Pantone + CMYK + Delta E + 印刷报价（2415 色）|
| [vtracer](https://github.com/visioncortex/vtracer) | Rust 矢量描图引擎 |

## License

MIT © AbinCheungCom
