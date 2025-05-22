FROM python:3.11.4-slim-bullseye AS prod


# 安装 Poetry 并配置镜像源
RUN pip install poetry==1.8.2 -i https://mirrors.aliyun.com/pypi/simple/ && \
    poetry config virtualenvs.create false && \
    poetry config cache-dir /tmp/poetry_cache && \
    poetry config repositories.pypi https://mirrors.aliyun.com/pypi/simple/  # 关键配置

# 设置 pip 默认镜像源
ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/

# 复制依赖文件并安装
COPY pyproject.toml poetry.lock /app/src/
WORKDIR /app/src
RUN --mount=type=cache,target=/tmp/poetry_cache poetry install --only main


# 复制应用代码并重新安装（确保代码变更触发依赖更新）
COPY . /app/src/
RUN --mount=type=cache,target=/tmp/poetry_cache poetry install --only main

CMD ["/usr/local/bin/python", "-m", "med_rag_server"]

# FROM prod AS dev
# RUN --mount=type=cache,target=/tmp/poetry_cache poetry install