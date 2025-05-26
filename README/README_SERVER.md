# med_rag_server

该项目是用于 RAG 服务的API。包含知识库构建，查询配置等。

## Poetry

该项目使用 poetry 进行依赖管理。Poetry 是一款现代化的依赖管理工具。

要运行该项目，请使用以下命令：

```bash
poetry install
poetry run python -m med_rag_server
```

这将在配置的主机上启动服务器。

您可以在 `/api/docs` 找到 Swagger 文档。

您可以在此处阅读更多关于 poetry 的信息：https://python-poetry.org/

## Docker

您可以使用以下命令通过 Docker 启动该项目：

```bash
docker-compose up --build
```

如果您想在 Docker 中进行开发，并启用自动重新加载和端口映射，请在 Docker 命令中添加 `-f deploy/docker-compose.dev.yml`，如下所示：

```bash
docker-compose -f docker-compose.yml -f deploy/docker-compose.dev.yml --project-directory . up --build
```

此命令将在端口 8000 上公开 Web 应用程序，挂载当前目录并启用自动重新加载。

但是，每次修改 `poetry.lock` 或 `pyproject.toml` 时，您都需要使用以下命令重新构建镜像：

```bash
docker-compose build
```

## 项目结构

```bash
$ tree "med_rag_server"
med_rag_server
├── conftest.py  # 所有测试的夹具。
├── db  # 包含数据库配置的模块
│   ├── dao  # 数据访问对象。包含与数据库交互的不同类。
│   └── models  # 包含 ORM 的不同模型的包。
├── __main__.py  # 启动脚本。启动 uvicorn。
├── services  # 不同外部服务的包，如 rabbit 或 redis 等。
├── settings.py  # 项目的主配置设置。
├── static  # 静态内容。
├── tests  # 项目的测试。
└── web  # 包含 Web 服务器的包。处理器、启动配置。
    ├── api  # 包含所有处理器的包。
    │   └── router.py  # 主路由器。
    ├── application.py  # FastAPI 应用程序配置。
    └── lifespan.py  # 包含在启动和关闭时要执行的操作。
```

## 配置

此应用程序可以通过环境变量进行配置。

您可以在根目录中创建 `.env` 文件，并在此处放置所有环境变量。

所有环境变量应以 "MED_RAG_SERVER_" 前缀开头。

例如，如果您在 "med_rag_server/settings.py" 中看到一个名为 `random_parameter` 的变量，您应该提供 "MED_RAG_SERVER_RANDOM_PARAMETER" 变量来配置值。可以通过覆盖 `med_rag_server.settings.Settings.Config` 中的 `env_prefix` 属性来更改此行为。

.env 文件的示例：
```bash
MED_RAG_SERVER_RELOAD="True"
MED_RAG_SERVER_PORT="8000"
MED_RAG_SERVER_ENVIRONMENT="dev"
```

您可以在此处阅读有关 BaseSettings 类的更多信息：https://pydantic-docs.helpmanual.io/usage/settings/

## Pre-commit

要在 shell 中安装 pre-commit，只需运行：
```bash
pre-commit install
```

pre-commit 在发布代码之前检查代码非常有用。它通过 .pre-commit-config.yaml 文件进行配置。

默认情况下，它运行：
* black（格式化您的代码）；
* mypy（验证类型）；
* ruff（发现可能的错误）；

您可以在此处阅读有关 pre-commit 的更多信息：https://pre-commit.com/

## 运行测试

如果您想在 Docker 中运行测试，只需运行：

```bash
docker-compose run --build --rm api pytest -vv .
docker-compose down
```

要在本地计算机上运行测试：
1. 您需要启动一个数据库。

我更喜欢使用 Docker 来完成：
```
docker run -p "5432:5432" -e "POSTGRES_PASSWORD=med_rag_server" -e "POSTGRES_USER=med_rag_server" -e "POSTGRES_DB=med_rag_server" postgres:16.3-bullseye
```

2. 运行 pytest。
```bash
pytest -vv .
```