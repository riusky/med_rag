# 使用官方 uv 基础镜像（已预装 uv 和 Python 3.12）
FROM ghcr.io/astral-sh/uv:python3.12-bookworm

# 设置阿里云镜像源
ENV UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/

# 复制 requirements.txt 和 应用代码
COPY requirements.txt /app/
COPY . /app/src/
WORKDIR /app/src

# 安装依赖
RUN uv pip install --system \
    -r /app/requirements.txt \
    --index-url $UV_INDEX_URL

# 安装项目自身（可编辑模式）
RUN uv pip install --system -e .

# 启动应用（根据项目入口调整）
CMD ["python", "-m", "med_rag_server"]