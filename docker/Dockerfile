# ColorFlow CLI Docker 镜像
# multi-stage build for minimal size

FROM python:3.12-slim as builder

WORKDIR /app

# 复制源码
COPY . .

# 安装依赖（仅安装 vtracer，跳过 API 依赖）
# 注意：版本约束必须加引号，否则 `>` 会被 shell 当作重定向符
RUN pip install --no-cache-dir "vtracer>=0.6.15" "pillow>=10.0.0"

# === 生产镜像 ===
FROM python:3.12-slim

WORKDIR /app

# 安装 vtracer（Rust 二进制）
RUN pip install --no-cache-dir "vtracer>=0.6.15" "pillow>=10.0.0"

# 复制 CLI 入口、SDK 源码，以及构建元数据（pip install /app 需要 pyproject.toml / README / LICENSE）
COPY --from=builder /app/cli /app/cli
COPY --from=builder /app/colorflow_sdk /app/colorflow_sdk
COPY --from=builder /app/pyproject.toml /app/README.md /app/LICENSE /app/

# 安装 CLI（构建 wheel 并注册 colorflow 命令）
RUN pip install --no-cache-dir /app

# 创建 data 目录
RUN mkdir -p /data

ENTRYPOINT ["colorflow"]
CMD ["--help"]
