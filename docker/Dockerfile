# ColorFlow CLI Docker 镜像
# multi-stage build for minimal size

FROM python:3.12-slim as builder

# 安装构建依赖
RUN pip install --no-cache-dir --user --break-system-packages pipx && \
    pipx install hatch

WORKDIR /app

# 复制源码
COPY . .

# 安装依赖（仅安装 vtracer，跳过 API 依赖）
RUN pip install --no-cache-dir vtracer>=0.6.0

# === 生产镜像 ===
FROM python:3.12-slim

WORKDIR /app

# 安装 vtracer（Rust 二进制）
RUN pip install --no-cache-dir vtracer>=0.6.0

# 复制 CLI 入口
COPY --from=builder /app/cli /app/cli
COPY --from=builder /app/colorflow_sdk /app/colorflow_sdk

# 安装 CLI
RUN pip install --no-cache-dir /app

# 创建 data 目录
RUN mkdir -p /data

ENTRYPOINT ["colorflow"]
CMD ["--help"]
