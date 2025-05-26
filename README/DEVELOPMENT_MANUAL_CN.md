以下是将开发手册翻译为中文的版本：

# 开发手册

## 目录

1. [简介](#简介)
    1.1. [项目概述](#项目概述)
    1.2. [目录结构](#目录结构)
2. [后端开发 (`server/`)](#后端开发-server)
    2.1. [安装配置](#后端安装配置)
    2.2. [启动后端开发服务器](#启动后端开发服务器)
    2.3. [配置管理](#后端配置管理)
    2.4. [数据库](#后端数据库)
        2.4.1. [数据库模型](#数据库模型)
        2.4.2. [数据访问对象 (DAO)](#数据访问对象-dao)
    2.5. [API 端点](#后端-api-端点)
        2.5.1. [API 模式](#后端-api-模式)
        2.5.2. [知识库 API (`/knowledge-bases`)](#知识库-api-knowledge-bases)
        2.5.3. [文档 API (`/document`)](#文档-api-document)
    2.6. [后端测试](#后端测试)
    2.7. [提交前检查](#后端提交前检查)
3. [前端开发 (`frontend/`)](#前端开发-frontend)
    3.1. [安装配置](#前端安装配置)
    3.2. [启动前端开发服务器](#启动前端开发服务器)
    3.3. [路由管理](#前端路由管理)
    3.4. [页面组件](#前端页面组件)
        3.4.1. [`index2.vue` (聊天界面)](#index2vue-聊天界面)
        3.4.2. [其他页面](#其他前端页面)
    3.5. [API 服务](#前端-api-服务)
        3.5.1. [HTTP 客户端配置 (`client.ts`)](#http-客户端配置-clientts)
        3.5.2. [医学 RAG 服务 (`medicalRag.ts`)](#医学-rag-服务-medicalragts)
        3.5.3. [知识库服务 (`knowledgeBase.ts`)](#知识库服务-knowledgebasets)
        3.5.4. [文档服务 (`document.ts`)](#文档服务-documentts)
    3.6. [状态管理 (Pinia)](#前端状态管理-pinia)
        3.6.1. [Pinia 配置 (`stores/index.ts`)](#pinia-配置-storesindexts)
        3.6.2. [认证存储 (`stores/auth.store.ts`)](#认证存储-storesauthstorets)
4. [工作流引擎 (`med-rag-flow/`)](#工作流引擎-med-rag-flow)
    4.1. [概述](#工作流概述)
    4.2. [配置](#工作流配置)
    4.3. [运行工作流](#运行工作流)

---

## 1. 简介

### 1.1. 项目概述
本项目是一个基于 Web 的医学检索增强生成（RAG）系统，包含三个主要组件：
- **后端服务器**：使用 FastAPI 构建，负责 API 逻辑、数据库交互和 RAG 流程协调
- **前端应用**：基于 Vue.js（使用 Bun 和 Vite），提供聊天、知识库管理和文档处理的用户界面
- **工作流引擎** (`med-rag-flow`)：使用 Python 和 Prefect 实现的批处理流程，用于 PDF 文档解析、分块、向量生成和后端集成

### 1.2. 目录结构
项目根目录包含：
- `frontend/`: Vue.js 前端应用
- `server/`: FastAPI 后端应用
- `med-rag-flow/`: 基于 Prefect 的数据处理流程
- 各 README 文件：组件专用说明文档

---

## 2. 后端开发 (`server/`)

### 2.1. 后端安装配置
**前提条件：**
* Python 3.9+
* Poetry 包管理器
* Docker

**步骤：**
1. 进入 server 目录
2. 使用 Poetry 安装依赖
3. 配置环境变量（复制 .env 文件）
4. 启动 Docker 数据库服务
5. 执行 Alembic 迁移
6. 安装 pre-commit 钩子

### 2.2. 启动后端开发服务器
```bash
poetry run uvicorn med_rag_server.web.application:get_app --reload --host 0.0.0.0 --port 8000
```

### 2.3. 后端配置管理
通过 `.env` 文件管理环境变量，包含：
- 数据库连接参数
- JWT 安全配置
- RAG 相关 API 配置
- 文件存储路径
- 日志级别

### 2.4. 后端数据库  
后端使用SQL数据库（通常为PostgreSQL），通过SQLAlchemy ORM进行管理，并使用Alembic处理数据迁移。

#### 2.4.1. 数据库模型  
位于`server/med_rag_server/db/models/`目录下。这些是SQLAlchemy声明式模型，用于表示数据库表。

*   **`KnowledgeBaseModel`（`knowledge_base_model.py`）：**  
    *   表示知识库，即文档的集合。  
    *   **关键字段：**  
        *   `id`（整数，主键）：知识库的唯一标识符。  
        *   `name`（字符串，非空，唯一）：用户定义的知识库名称。  
        *   `description`（文本，可为空）：可选描述。  
        *   `created_at`（日期时间，非空，默认值：当前时间）：创建时间戳。  
        *   `updated_at`（日期时间，非空，默认值：当前时间，更新时自动设置为当前时间）：最后更新时间戳。  
        *   `documents`（关系）：与`DocumentModel`的一对多关系。一个知识库可包含多个文档。  
        *   `vector_storage_path`（字符串，可为空）：与此知识库关联的向量嵌入文件系统或对象存储路径。  
        *   `processing_status`（字符串，可为空，默认值："pending"）：表示此知识库文档处理状态（如"pending"、"processing"、"completed"、"failed"）。  

*   **`DocumentModel`（`document_model.py`）：**  
    *   表示知识库中的单个文档。  
    *   **关键字段：**  
        *   `id`（整数，主键）：文档的唯一标识符。  
        *   `name`（字符串，非空）：文档名称（如文件名）。  
        *   `kb_id`（整数，外键指向`knowledge_bases.id`，非空）：此文档所属知识库的ID。  
        *   `file_path`（字符串，非空）：原始文档文件的路径。  
        *   `file_type`（字符串，可为空）：文件的MIME类型或扩展名（如"application/pdf"、"text/plain"）。  
        *   `status`（字符串，可为空，默认值："pending"）：文档处理状态（如"pending"、"processing"、"completed"、"failed"）。  
        *   `created_at`（日期时间，非空，默认值：当前时间）：创建时间戳。  
        *   `updated_at`（日期时间，非空，默认值：当前时间，更新时自动设置为当前时间）：最后更新时间戳。  
        *   `knowledge_base`（关系）：与`KnowledgeBaseModel`的多对一关系。  
        *   `metadata_`（JSON，可为空）：存储文档的附加元数据（如作者、页数、自定义标签）。使用`metadata_`命名以避免与SQLAlchemy的`metadata`属性冲突。

#### 2.4.2. 数据访问对象（DAOs）
位于`server/med_rag_server/db/dao/`目录下。DAO封装了与数据库模型交互的逻辑，提供CRUD（创建、读取、更新、删除）接口。

*   **`KnowledgeBaseDAO` (`knowledge_base_dao.py`):**
    *   提供与`KnowledgeBaseModel`表交互的方法。
    *   **关键方法：**
        *   `create_knowledge_base_model(name: str, description: Optional[str] = None, vector_storage_path: Optional[str] = None, processing_status: Optional[str] = "pending") -> KnowledgeBaseModel`: 创建新知识库。
        *   `get_knowledge_base_model(kb_id: int) -> Optional[KnowledgeBaseModel]`: 通过ID检索知识库。
        *   `get_knowledge_base_model_by_name(name: str) -> Optional[KnowledgeBaseModel]`: 通过名称检索知识库。
        *   `get_all_knowledge_base_models(limit: int = 10, offset: int = 0) -> List[KnowledgeBaseModel]`: 获取分页的知识库列表。
        *   `update_knowledge_base_model(kb_id: int, name: Optional[str] = None, description: Optional[str] = None, vector_storage_path: Optional[str] = None, processing_status: Optional[str] = None) -> Optional[KnowledgeBaseModel]`: 更新现有知识库。
        *   `delete_knowledge_base_model(kb_id: int) -> bool`: 通过ID删除知识库。

*   **`DocumentDAO` (`document_dao.py`):**
    *   提供与`DocumentModel`表交互的方法。
    *   **关键方法：**
        *   `create_document_model(name: str, kb_id: int, file_path: str, file_type: Optional[str] = None, status: Optional[str] = "pending", metadata_: Optional[dict] = None) -> DocumentModel`: 创建新文档。
        *   `get_document_model(doc_id: int) -> Optional[DocumentModel]`: 通过ID检索文档。
        *   `get_documents_by_kb_id(kb_id: int, limit: int = 10, offset: int = 0) -> List[DocumentModel]`: 检索属于特定知识库的所有文档。
        *   `update_document_model(doc_id: int, name: Optional[str] = None, status: Optional[str] = None, metadata_: Optional[dict] = None) -> Optional[DocumentModel]`: 更新现有文档。
        *   `delete_document_model(doc_id: int) -> bool`: 通过ID删除文档。
        *   `delete_documents_by_kb_id(kb_id: int) -> int`: 删除与给定知识库ID关联的所有文档，并返回删除的文档数量。

*   **`DummyDAO` (`dummy_dao.py`):**
    *   提供与`DummyModel`表交互的方法。
    *   **关键方法：**
        *   `create_dummy_model(name: str) -> None`: 创建新的虚拟模型实例。
        *   `get_all_dummy_models(limit: int = 10, offset: int = 0) -> List[DummyModel]`: 获取分页的虚拟模型列表。
        *   `get_dummy_model(dummy_id: int) -> Optional[DummyModel]`: 通过ID检索特定的虚拟模型。

### 2.5. 后端API端点  
定义于`server/med_rag_server/web/api/`目录。这些模块包含FastAPI路由器和端点逻辑。  

#### 2.5.1. 后端API模式  
位于`server/med_rag_server/web/api/schemas/`目录。这些是用于请求和响应验证、序列化和文档化的Pydantic模型。  

*   **知识库模式（`knowledge_base.py`）：**  
    *   `KnowledgeBaseBase`（Pydantic BaseModel）：包含公共字段的基础模式。  
        *   `name`: str  
        *   `description`: Optional[str] = None  
        *   `vector_storage_path`: Optional[str] = None  
        *   `processing_status`: Optional[str] = "pending"  
    *   `KnowledgeBaseCreate`（继承自`KnowledgeBaseBase`）：用于创建新知识库的模式。  
    *   `KnowledgeBaseUpdate`（继承自`KnowledgeBaseBase`）：用于更新现有知识库的模式，字段可选。  
    *   `KnowledgeBaseInDB`（继承自`KnowledgeBaseBase`）：用于数据库存储数据的模式，包含`id`。  
        *   `id`: int  
    *   `KnowledgeBaseResponse`（继承自`KnowledgeBaseInDB`）：用于API响应的模式，通常包含`id`、`name`、`description`、`created_at`、`updated_at`、`processing_status`等字段。  
        *   `created_at`: datetime  
        *   `updated_at`: datetime  
    *   `KnowledgeBaseListResponse`（Pydantic BaseModel）：用于知识库列表的模式，通常包含分页信息。  
        *   `data`: List[KnowledgeBaseResponse]  
        *   `total`: int  

*   **文档模式（`document.py`）：**  
    *   `DocumentBase`（Pydantic BaseModel）：包含公共文档字段的基础模式。  
        *   `name`: str  
        *   `file_type`: Optional[str] = None  
        *   `status`: Optional[str] = "pending"  
        *   `metadata_`: Optional[dict] = None  
    *   `DocumentCreate`（继承自`DocumentBase`）：用于创建新文档的模式（上传文档到知识库时使用）。  
        *   `kb_id`: int（隐式字段，文档通常在知识库上下文中创建）  
        *   `file_path`: str（内部字段，通常不直接用于客户端请求）  
    *   `DocumentUpdate`（继承自`DocumentBase`）：用于更新文档元数据的模式，字段可选。  
    *   `DocumentInDB`（继承自`DocumentBase`）：用于数据库中文档数据的模式。  
        *   `id`: int  
        *   `kb_id`: int  
        *   `file_path`: str  
    *   `DocumentResponse`（继承自`DocumentInDB`）：用于单个文档API响应的模式。  
        *   `created_at`: datetime  
        *   `updated_at`: datetime  
    *   `DocumentListResponse`（Pydantic BaseModel）：用于文档列表的模式。  
        *   `data`: List[DocumentResponse]  
        *   `total`: int  
    *   `MedicalRagQuery`（Pydantic BaseModel）：用于查询医疗RAG系统的模式。  
        *   `question`: str  
        *   `kb_id`: int（要查询的知识库ID）  
        *   `language`: Optional[Literal['zh', 'en']] = 'zh'  
        *   `require_references`: Optional[bool] = True  
        *   `safety_warnings`: Optional[bool] = True  
    *   `Reference`（Pydantic BaseModel）：用于RAG响应中参考源的模式。  
        *   `text`: str  
        *   `source`: str  
    *   `MedicalRagResponseMetadata`（Pydantic BaseModel）：用于RAG响应元数据的模式。  
        *   `doc_count`: int  
        *   `kb_id`: int  
        *   `vector_path`: Optional[str]  
    *   `MedicalRagResponse`（Pydantic BaseModel）：用于完整RAG响应的模式。  
        *   `answer`: str  
        *   `references`: List[Reference]  
        *   `metadata`: MedicalRagResponseMetadata  

#### 2.5.2. 知识库API（`/knowledge-bases`）  
路由前缀：`/api/knowledge-bases`。由`server/med_rag_server/web/api/knowledge_base/views.py`处理。  

*   **`POST /`**：创建新知识库。  
    *   请求体：`KnowledgeBaseCreate`模式。  
    *   响应：`KnowledgeBaseResponse`模式。  
    *   摘要：接收知识库名称和可选描述，返回创建的知识库对象。  
*   **`GET /`**：分页列出所有知识库。  
    *   查询参数：`limit`（int，默认10）、`offset`（int，默认0）。  
    *   响应：`KnowledgeBaseListResponse`模式（包含`KnowledgeBaseResponse`列表）。  
    *   摘要：获取分页的知识库列表。  
*   **`GET /{kb_id}`**：根据ID获取特定知识库。  
    *   路径参数：`kb_id`（int）。  
    *   响应：`KnowledgeBaseResponse`模式。  
    *   摘要：获取单个知识库的详细信息。  
*   **`PUT /{kb_id}`**：更新知识库。  
    *   路径参数：`kb_id`（int）。  
    *   请求体：`KnowledgeBaseUpdate`模式。  
    *   响应：`KnowledgeBaseResponse`模式。  
    *   摘要：更新知识库的名称、描述或其他可变字段。  
*   **`DELETE /{kb_id}`**：删除知识库。  
    *   路径参数：`kb_id`（int）。  
    *   响应：成功时返回状态码204（无内容）或错误信息。  
    *   摘要：删除知识库及其关联的文档和向量数据（具体实现可能不同）。  
*   **`POST /{kb_id}/upload-document`**：上传文档到特定知识库。  
    *   路径参数：`kb_id`（int）。  
    *   请求：`UploadFile`（FastAPI的文件上传类型）。  
    *   响应：`DocumentResponse`模式（用于创建的文档记录）。  
    *   摘要：上传文件，保存并创建文档记录，可能触发处理流程。  
*   **`GET /{kb_id}/documents`**：列出特定知识库中的文档。  
    *   路径参数：`kb_id`（int）。  
    *   查询参数：`limit`（int，默认10）、`offset`（int，默认0）。  
    *   响应：`DocumentListResponse`模式。  
    *   摘要：获取指定知识库的分页文档列表。

#### 2.5.3. 文档API (`/document`)  
路由前缀：`/api/document`，由`server/med_rag_server/web/api/document/views.py`处理。  

*   **`GET /{doc_id}`**：通过ID获取特定文档。  
    *   路径参数：`doc_id`（整数）。  
    *   响应：`DocumentResponse`模式。  
    *   摘要：检索单个文档的详细信息。  
*   **`PUT /{doc_id}`**：更新文档元数据。  
    *   路径参数：`doc_id`（整数）。  
    *   请求体：`DocumentUpdate`模式。  
    *   响应：`DocumentResponse`模式。  
    *   摘要：更新文档的可变字段，如名称或状态。  
*   **`DELETE /{doc_id}`**：删除文档。  
    *   路径参数：`doc_id`（整数）。  
    *   响应：成功时返回状态码204（无内容）或错误消息。  
    *   摘要：删除文档记录及其关联文件。  
*   **`POST /medical-search-stream`**：执行医学RAG查询并返回流式响应。  
    *   请求体：`MedicalRagQuery`模式。  
    *   响应：`StreamingResponse`（服务器发送事件）。  
        *   事件：  
            *   `event: data, data: {"delta": "文本块"}`（用于流式回答）  
            *   `event: references, data: {"sources": ["来源1", "来源2"]}`（用于参考文献）  
            *   `event: complete, data: {"metadata": {"doc_count": N, "kb_id": X, ...}}`（表示流结束并附带元数据）  
            *   `event: error, data: {"error": "消息"}`（如果发生错误）  
    *   摘要：接收问题和知识库ID，流式返回RAG答案、参考文献和元数据。  

### 2.6. 后端测试  
*   **框架**：Pytest通常用于测试FastAPI应用。  
*   **位置**：测试通常位于`server/tests/`目录。  
*   **结构**：  
    *   `tests/api/`：API端点的集成测试。  
    *   `tests/db/`：数据库DAO和模型的单元测试。  
    *   `tests/services/`：业务逻辑/服务的单元测试。  
    *   `tests/conftest.py`：包含测试夹具（如测试数据库设置、API客户端）。  
*   **运行测试**：  
    ```bash  
    poetry run pytest  
    ```  
    或运行带覆盖率的测试：  
    ```bash  
    poetry run pytest --cov=med_rag_server  
    ```  
*   **关键测试内容**：  
    *   API端点响应（状态码、JSON结构、数据正确性）。  
    *   认证和授权逻辑。  
    *   数据库交互（DAO中的CRUD操作）。  
    *   服务中的业务逻辑。  
    *   错误处理。  
*   **测试数据库**：测试通常使用单独的测试数据库（如临时SQLite数据库或专用PostgreSQL测试数据库），以避免干扰开发数据库。`conftest.py`中的夹具管理测试数据库的设置和清理，并提供用于API请求的测试客户端。  

### 2.7. 后端预提交钩子  
*   **目的**：在提交代码前自动执行代码质量检查（如代码风格、格式化、类型检查）。  
*   **配置**：定义在`server/.pre-commit-config.yaml`中。  
*   **常用钩子**：  
    *   **Black**：用于统一的代码格式化。  
    *   **Flake8**：用于强制执行PEP 8风格指南和错误检测。  
    *   **isort**：用于自动排序导入。  
    *   **MyPy**：用于静态类型检查。  
    *   **Prettier**：（如适用，用于JSON、YAML、MD文件）。  
    *   检测大文件、尾随空格等的钩子。  
*   **安装**：  
    ```bash  
    poetry run pre-commit install  
    ```  
    这会将钩子安装到本地Git仓库中。提交更改时，钩子会自动运行。如果钩子失败，提交将被中止，以便修复问题。  
*   **手动执行**：  
    可以手动对所有文件运行所有预提交钩子：  
    ```bash  
    poetry run pre-commit run --all-files  
    ```

---

## 3. 前端开发 (`frontend/`)

### 3.1. 前端环境配置与安装
前端采用Vue.js框架构建，使用Vite作为打包工具，Bun作为JavaScript运行时/包管理器。

**环境要求：**
*   Bun（JavaScript运行时和工具包）
*   Node.js和npm（若需在生产/预发布环境使用PM2进行进程管理）

**配置步骤：**
1.  **进入前端目录：**
    ```bash
    cd frontend/
    ```
2.  **使用Bun安装依赖：**
    ```bash
    bun install
    ```
3.  **环境变量配置（`.env`文件）：**
    *   Vue.js项目（特别是基于Vite构建的）通过`.env`文件管理环境变量（如`.env`、`.env.development`、`.env.production`）
    *   常用变量：
        *   `VITE_BASE_URL`：后端API基础地址（例如`http://localhost:8000/api`）
        *   其他前端所需的API密钥或功能开关
    *   如需本地覆盖配置，可创建`.env.local`或`.env.development.local`（通常被git忽略）。示例：
        ```
        VITE_BASE_URL=http://localhost:8000/api 
        ```
        （注意：Vite要求暴露给客户端的变量必须以`VITE_`为前缀）

### 3.2. 运行前端开发服务器  
1.  **进入 `frontend/` 目录。**  
2.  **使用 Bun 运行开发服务器：**  
    ```bash  
    bun run dev  
    ```  
    此命令通常会启动 Vite 开发服务器。  
3.  前端应用通常可通过 `http://localhost:5173` 访问（Vite 默认端口，可能因配置而异）。控制台输出会显示正确的访问地址。  

**生产/预发布环境替代方案（使用 PM2）：**  
若使用 PM2（Node.js 进程管理器）：  
1.  **确保已安装 Node.js 和 npm。**  
2.  **全局安装 PM2：**  
    ```bash  
    npm install pm2 -g  
    ```  
3.  **构建生产环境前端应用：**  
    ```bash  
    bun run build  
    ```  
    此操作会生成包含优化静态资源的 `dist/` 目录。  
4.  **使用静态服务器（如 `serve`）或配置 PM2 托管构建产物。**  
    若使用简易 Node.js 服务器托管构建文件，可配置 `ecosystem.config.js` 供 PM2 使用：  
    ```javascript  
    // ecosystem.config.js  
    module.exports = {  
      apps : [{  
        name   : "frontend-app",  
        script : "npm", // 或指向 server.js 等服务器脚本的路径  
        args   : "run start:prod", // 若有特定生产启动脚本  
        // 若使用简易服务器托管静态文件：  
        // script : "npx",  
        // args   : "serve -s dist -l 3000",   
        cwd    : "./frontend", // 工作目录  
        watch  : false,  
        env_production: {  
           NODE_ENV: "production",  
           PORT: 3000 // 示例端口  
        }  
      }]  
    }  
    ```  
    随后通过 PM2 启动：  
    ```bash  
    pm2 start ecosystem.config.js --env production  
    ```

### 3.3. 前端路由  
路由由 `vue-router` 管理，主要配置通常位于 `frontend/src/router/index.ts`。  

*   **路由配置 (`frontend/src/router/index.ts`):**  
    *   从 `vue-router` 导入 `createRouter`、`createWebHistory`（或 `createWebHashHistory`）。  
    *   定义 `RouteRecordRaw` 对象数组。  
    *   初始化路由实例：  
        ```typescript  
        import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'  
        import HomeView from '../views/HomeView.vue' // 示例导入  

        const routes: Array<RouteRecordRaw> = [  
          // ... 路由定义  
        ]  

        const router = createRouter({  
          history: createWebHistory(import.meta.env.BASE_URL), // BASE_URL 通常来自 Vite 配置  
          routes  
        })  

        export default router  
        ```  
    *   该路由实例随后在 `main.ts` 中使用（`app.use(router)`）。  

*   **导航守卫/中间件:**  
    *   全局导航守卫（如 `router.beforeEach`）可在 `router/index.ts` 或单独的中间件文件中定义。  
    *   用于身份验证检查（如未认证则重定向到登录页）、设置面包屑或埋点统计等任务。  
    *   示例：  
        ```typescript  
        import { useAuthStore } from '@/stores/auth.store' // 假设使用 Pinia 状态管理  

        router.beforeEach(async (to, from, next) => {  
          const authStore = useAuthStore()  
          const requiresAuth = to.meta.requiresAuth ?? false  
          const publicPages = ['/login', '/register'] // 示例公开页面  

          if (requiresAuth && !authStore.isAuthenticated) {  
            if (!publicPages.includes(to.path)) {  
              return next({ path: '/login', query: { redirect: to.fullPath } })  
            }  
          }  
          // 若存在 token 但未加载用户数据，可在此处获取用户信息  
          // if (authStore.token && !authStore.user) {  
          //   await authStore.fetchUser();  
          // }  
          next()  
        })  
        ```  
    *   也可在特定路由记录中定义独享守卫（`beforeEnter`）。  

*   **路由定义表:**  
    `routes` 数组包含多个路由对象，每个对象定义如下：  
    | 路径                | 名称         | 组件（视图）         | `meta`（示例）                  | 懒加载？     |  
    | ------------------- | ------------ | -------------------- | ------------------------------- | ------------ |  
    | `/`                 | `Home`       | `HomeView.vue`       | `{ requiresAuth: true }`        | 否（示例）   |  
    | `/chat`             | `Chat`       | `Index2View.vue`     | `{ requiresAuth: true }`        | 是           |  
    | `/kb`               | `KBList`     | `KbListView.vue`     | `{ requiresAuth: true }`        | 是           |  
    | `/kb/create`        | `KBCreate`   | `KbCreateView.vue`   | `{ requiresAuth: true }`        | 是           |  
    | `/kb/:id`           | `KBDetail`   | `KbDetailView.vue`   | `{ requiresAuth: true, props:true}`| 是           |  
    | `/kb/:id/upload`    | `KBUpload`   | `KbUploadView.vue`   | `{ requiresAuth: true, props:true}`| 是           |  
    | `/documents`        | `DocList`    | `DocListView.vue`    | `{ requiresAuth: true }`        | 是           |  
    | `/documents/:id`    | `DocDetail`  | `DocDetailView.vue`  | `{ requiresAuth: true, props:true}`| 是           |  
    | `/:pathMatch(.*)*` | `NotFound`   | `NotFoundView.vue`   |                                 | 是           |  

    *懒加载路由示例:*  
    ```typescript  
    {  
      path: '/chat',  
      name: 'Chat',  
      component: () => import('@/pages/index2.vue'), // 懒加载  
      meta: { requiresAuth: true }  
    }  
    ```

### 3.4. 前端页面  
位于`frontend/src/pages/`或`frontend/src/views/`目录下，这些是由`vue-router`渲染的主要Vue组件。

#### 3.4.1. `index2.vue`（聊天界面）  
文件路径：`frontend/src/pages/index2.vue`  

这是用户与RAG系统交互的主要界面。  

*   **布局：**  
    *   使用`ResizablePanelGroup`实现多面板布局。  
    *   **左侧面板：**显示对话历史记录。  
        *   列出过往对话的标题和时间戳。  
        *   允许选择对话以查看消息内容。  
        *   提供"新建聊天"按钮以开始新对话。  
    *   **右侧面板（主区域）：**  
        *   **聊天内容区：**显示当前活跃对话的消息。  
            *   用户消息通常右对齐。  
            *   助手消息左对齐，包含以下元素：  
                *   头像。  
                *   标签页（"回复内容"、"文档引用"和"原始图片"（如适用））。  
                *   **回复内容标签页：**展示Markdown渲染的RAG响应（使用`v-md-preview`）。  
                *   **文档引用标签页：**显示RAG模型使用的参考内容。每个引用包含来源及可选文本片段。  
                *   每条消息的时间戳。  
        *   **输入区：**  
            *   文本输入框（支持Shift+Enter换行）。  
            *   知识库选择下拉菜单（`Select`组件）。  
            *   操作按钮（如附件、Sparkles、设置等）。  
            *   "发送"按钮（加载状态显示旋转图标和"发送中..."文字）。  

*   **核心脚本逻辑（`<script setup lang="ts">`）：**  
    *   **状态管理：**  
        *   `conversations`: `ref<Conversation[]>`存储所有对话线程。  
        *   `activeIndex`: `ref<number>`表示当前选中的对话索引。  
        *   `inputMessage`: `ref<string>`存储用户在输入框中的当前消息。  
        *   `selectedKbId`: `ref<number>`表示选中的知识库ID。  
        *   `knowledgeBases`: `ref<KnowledgeBase[]>`存储可用知识库列表。  
        *   `isLoading`: `ref<boolean>`管理API调用时的加载状态。  
    *   **计算属性：**  
        *   `activeMessages`: 根据`conversations`和`activeIndex`计算当前对话的消息列表。  
    *   **API调用：**  
        *   `sendMessage()`:  
            *   将`isLoading`设为`true`。  
            *   构建用户消息并添加到`activeMessages`。  
            *   创建响应式`assistantMessage`对象。  
            *   调用`medicalRag.ts`中的`apiMedicalRag.streamQuery()`。  
            *   处理流式数据（`onData`）：将增量内容追加到`assistantMessage.content`。  
            *   处理完成事件（`onComplete`）：设置最终内容和引用，将`isLoading`设为`false`。  
            *   处理错误（`onError`）：显示错误信息，将`isLoading`设为`false`。  
        *   组件挂载时（`onMounted`）通过`apiKnowledgeBase.getList()`获取知识库列表。  
    *   **组件交互：**  
        *   `newConversation()`: 创建新的空对话对象并设为活跃状态。  
        *   `selectConversation()`: 修改`activeIndex`。  
        *   `handleKeydown()`: 管理输入框中的Enter/Shift+Enter行为。  
        *   `smartScroll()`: 自动滚动聊天区至最新消息。  
    *   **工具函数：**  
        *   `formatDate()`、`formatTime()`用于时间格式化显示。  
    *   **Markdown渲染：**使用`@kangc/v-md-editor`渲染助手的Markdown响应。  

#### 3.4.2. 其他前端页面  
其他作为页面的Vue组件简要说明：  

*   **知识库管理页面：**  
    *   **`KbListView.vue` (`/kb`):** 展示可用知识库列表，支持查看详情、编辑或删除。可能通过`knowledgeBase.ts` API服务获取数据，显示知识库名称、描述、状态及文档数量。  
    *   **`KbCreateView.vue` (`/kb/create`):** 创建新知识库的表单（名称、描述等），通过`knowledgeBase.ts`提交数据。  
    *   **`KbDetailView.vue` (`/kb/:id`):** 展示特定知识库的详情，包括文档列表、状态，以及上传新文档或触发重新处理的选项。  
    *   **`KbUploadView.vue` (`/kb/:id/upload`):** 提供文件拖放区等界面，用于向指定知识库上传文档，与文档上传API端点交互。  
*   **文档管理页面（可选，如果与知识库视图分离）：**  
    *   **`DocListView.vue` (`/documents`):** 可能列出所有知识库的文档或支持筛选。  
    *   **`DocDetailView.vue` (`/documents/:id`):** 展示特定文档的详情、内容（如可查看）、元数据和状态。  
*   **`NotFoundView.vue` (`/:pathMatch(.*)*`):** 通用"404未找到"页面。

### 3.5. 前端API服务  
位于`frontend/src/api/`目录下的TypeScript模块，封装了向后端发起HTTP请求的逻辑。  

#### 3.5.1. HTTP客户端配置 (`client.ts`)  
文件：`frontend/src/api/client.ts`  

*   **用途：** 配置并导出一个Axios实例用于发起HTTP请求。  
*   **核心功能：**  
    *   **基础URL：** 通过`import.meta.env.VITE_BASE_URL`设置所有请求的基准URL。  
    *   **请求头：** 默认请求头（如`Content-Type: application/json`）。  
    *   **拦截器：**  
        *   **请求拦截器：** 若用户已认证，则从Pinia存储或localStorage获取JWT令牌并添加到`Authorization`请求头。  
        *   **响应拦截器：** 处理全局错误响应（例如401未授权时跳转登录页，403禁止访问，500服务器错误提示等），也可用于响应数据转换。  
    *   **超时设置：** 默认请求超时时间。  
*   **示例代码：**  
    ```typescript  
    import axios, { type AxiosInstance, type InternalAxiosRequestConfig, type AxiosResponse } from 'axios'  
    import { useAuthStore } from '@/stores/auth.store' // 假设使用Pinia存储  

    const apiClient: AxiosInstance = axios.create({  
      baseURL: import.meta.env.VITE_BASE_URL || '/api',  
      headers: {  
        'Content-Type': 'application/json'  
      }  
    })  

    apiClient.interceptors.request.use(  
      (config: InternalAxiosRequestConfig) => {  
        const authStore = useAuthStore()  
        if (authStore.token) {  
          config.headers.Authorization = `Bearer ${authStore.token}`  
        }  
        return config  
      },  
      (error) => {  
        return Promise.reject(error)  
      }  
    )  

    apiClient.interceptors.response.use(  
      (response: AxiosResponse) => response, // 或直接返回response.data  
      async (error) => {  
        const authStore = useAuthStore()  
        if (error.response?.status === 401) {  
          authStore.logout() // 或尝试刷新令牌  
          // 可跳转至登录页：router.push('/login')  
        }  
        return Promise.reject(error)  
      }  
    )  

    export default apiClient  
    ```  

#### 3.5.2. 医疗RAG服务 (`medicalRag.ts`)  
文件：`frontend/src/api/medicalRag.ts`  

*   **用途：** 处理与医疗RAG功能相关的API调用，特别是流式聊天查询。  
*   **核心接口/类型：**  
    *   `MedicalRagQuery`：定义查询负载结构（问题、知识库ID、语言等），与后端Pydantic模型匹配。  
    *   `Reference`：定义参考文献对象结构（`{ text: string, source: string }`）。  
    *   `MedicalRagResponseMetadata`：RAG响应中的元数据结构。  
*   **`SSEParser`类：**  
    *   用于解析服务器推送事件（SSE）流的工具类。  
    *   `constructor(config: { onMessage: (event: MessageEvent) => void, onError: (error: string) => void })`  
    *   `feed(chunk: string)`：处理流式数据块，缓冲并提取完整的SSE消息（事件类型与数据）。  
    *   `processBuffer()`：内部方法，解析缓冲区的完整事件。  
*   **`apiMedicalRag.streamQuery()`方法：**  
    *   `async streamQuery(payload: MedicalRagQuery, handlers: { onData, onComplete, onError })`  
    *   使用`fetch` API向后端`/document/medical-search-stream`端点发起POST请求。  
    *   处理流式响应：  
        *   从`response.body`获取`ReadableStreamDefaultReader`。  
        *   读取流数据块（`reader.read()`）。  
        *   解码数据块（`TextDecoder`）并输入`SSEParser`实例。  
    *   `SSEParser`调用以下处理器：  
        *   `onData(delta: string)`：响应`event: data`（流式答案片段）。  
        *   `onComplete({ references: Reference[], ...metadata })`：合并`event: references`（含`{"sources":[]}`）和`event: complete`（含元数据）为单次调用，传递正确的`Reference[]`结构。  
        *   `onError(error: string)`：响应`event: error`或流解析错误。  
*   **数据转换逻辑：**  
    *   初始化`let collectedReferences: Reference[] = []`。  
    *   当收到SSE事件`event: references`且数据为`{"sources": ["s1", "s2"]}`时，将`sources`映射为`[{source: "s1", text: "s1"}, {source: "s2", text: "s2"}]`并存储到`collectedReferences`。  
    *   当收到SSE事件`event: complete`（含元数据但无参考文献数据），调用`handlers.onComplete`并传入`collectedReferences`和元数据。

#### 3.5.3. 知识库服务 (`knowledgeBase.ts`)
文件路径: `frontend/src/api/knowledgeBase.ts`

*   **功能:** 处理知识库的增删改查操作。
*   **依赖:** `apiClient` (配置好的Axios实例)。
*   **核心接口/类型:** 
    *   `KnowledgeBase` (或来自后端schema的`KnowledgeBaseResponse`): 知识库对象结构。
    *   `KnowledgeBaseCreate`, `KnowledgeBaseUpdate`: 请求负载类型。
*   **核心方法:** 
    *   `getList(params: { limit?: number, offset?: number }): Promise<AxiosResponse<{ data: KnowledgeBase[], total: number }>>`: 获取知识库列表。
        *   `GET /knowledge-bases`
    *   `getById(id: number): Promise<AxiosResponse<KnowledgeBase>>`: 获取单个知识库。
        *   `GET /knowledge-bases/${id}`
    *   `create(data: KnowledgeBaseCreate): Promise<AxiosResponse<KnowledgeBase>>`: 创建新知识库。
        *   `POST /knowledge-bases`
    *   `update(id: number, data: KnowledgeBaseUpdate): Promise<AxiosResponse<KnowledgeBase>>`: 更新知识库。
        *   `PUT /knowledge-bases/${id}`
    *   `delete(id: number): Promise<AxiosResponse<void>>`: 删除知识库。
        *   `DELETE /knowledge-bases/${id}`
    *   `uploadDocument(kbId: number, file: File, onUploadProgress?: (progressEvent: any) => void): Promise<AxiosResponse<DocumentResponse>>`: 上传文档到知识库。
        *   `POST /knowledge-bases/${kbId}/upload-document` (使用`FormData`进行文件上传)
    *   `getKbDocuments(kbId: number, params: { limit?: number, offset?: number }): Promise<AxiosResponse<{ data: DocumentResponse[], total: number }>>`: 获取指定知识库的文档列表。
        *   `GET /knowledge-bases/${kbId}/documents`

#### 3.5.4. 文档服务 (`document.ts`)
文件路径: `frontend/src/api/document.ts`

*   **功能:** 处理单个文档的增删改查操作（若未被`knowledgeBase.ts`完全覆盖）。
*   **依赖:** `apiClient`。
*   **核心接口/类型:** 
    *   `DocumentResponse`, `DocumentUpdate`: 文档结构及请求负载类型。
*   **核心方法示例:** 
    *   `getById(id: number): Promise<AxiosResponse<DocumentResponse>>`: 获取单个文档。
        *   `GET /document/${id}`
    *   `update(id: number, data: DocumentUpdate): Promise<AxiosResponse<DocumentResponse>>`: 更新文档元数据。
        *   `PUT /document/${id}`
    *   `delete(id: number): Promise<AxiosResponse<void>>`: 删除文档。
        *   `DELETE /document/${id}`

### 3.6. 前端状态管理 (Pinia)  
位于 `frontend/src/stores/` 目录下。Pinia 用于集中式状态管理。  

#### 3.6.1. Pinia 初始化 (`stores/index.ts`)  
文件：`frontend/src/stores/index.ts`  

*   **用途：** 初始化并导出主 Pinia 实例。  
*   **示例结构：**  
    ```typescript  
    import { createPinia } from 'pinia'  
    // 若使用持久化插件，可在此导入  
    // import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'  

    const pinia = createPinia()  
    // if (piniaPluginPersistedstate) {  
    //   pinia.use(piniaPluginPersistedstate)  
    // }  

    export default pinia  
    ```  
*   该 `pinia` 实例需在 `main.ts` 中引入（`app.use(pinia)`）。

---

## 4. 工作流引擎 (`med-rag-flow/`)

### 4.1. 工作流概览
`med-rag-flow/`目录包含一个基于Python和Prefect构建的数据处理管道，其主要功能是批量处理PDF文档以集成到RAG系统中。

**核心功能：**
1. **文档摄取：** 监控指定输入目录（如`med-rag-flow/input_pdfs/`）中的新增PDF文件
2. **解析：** 从PDF文档中提取文本内容
3. **分块：** 将提取的文本分割成适合向量嵌入的小块
4. **向量生成：** 使用指定嵌入模型（如Sentence Transformers）将文本块转换为数值向量
5. **存储：** 将生成的向量存入向量数据库（如FAISS、ChromaDB、Milvus），并将索引保存到与知识库ID关联的路径
6. **后端集成：** 与FastAPI后端通信实现：
    * 在主数据库中创建或更新文档记录
    * 更新知识库和文档状态（如"处理中"、"已完成"）
    * 存储相关知识库生成向量索引的路径

**工作流触发方式：**
* 支持手动触发
* 可配置定期运行（如每日）
* 当新文档上传到知识库的"暂存"区域时，可能通过后端API调用触发

### 4.2. 工作流设置  
**先决条件:**  
*   Python 3.9+  
*   Poetry（用于管理此子项目的Python依赖，如需隔离）或`requirements.txt`文件  

**步骤:**  
1.  **进入工作流目录:**  
    ```bash  
    cd med-rag-flow/  
    ```  
2.  **安装依赖项:**  
    *   使用Poetry: `poetry install`  
    *   使用`requirements.txt`: `pip install -r requirements.txt`  
    *   关键依赖包括: `prefect`、`langchain`（或类似文本分块/嵌入工具）、PDF解析库（`pypdf2`、`pdfminer.six`）、向量数据库客户端、HTTP客户端（`requests`、`httpx`）。  
3.  **配置（`config.py`或`.env`）:**  
    *   `INPUT_PDF_DIR`: 存放新PDF文件的目录路径。  
    *   `PROCESSED_DIR`: 成功处理后移动PDF文件的路径。  
    *   `FAILED_DIR`: 处理失败时移动PDF文件的路径。  
    *   `VECTOR_STORE_BASE_PATH`: 保存生成向量索引的基础路径。  
    *   `EMBEDDING_MODEL_NAME`: 句子转换模型的名称或路径。  
    *   `CHUNK_SIZE`、`CHUNK_OVERLAP`: 文本分块的参数。  
    *   `BACKEND_API_URL`: 用于更新的FastAPI后端URL。  
    *   `LOG_LEVEL`: 日志级别。  
4.  **Prefect设置（本地）:**  
    *   确保已安装Prefect。  
    *   可能需要配置Prefect后端（如本地SQLite服务器、Prefect Cloud）。简单本地执行时默认配置可能足够。  
    *   `prefect server start`（如需启动本地Prefect Orion/UI服务器进行监控）。

### 4.3. 运行工作流  
工作流通过Python脚本定义，使用Prefect的`@flow`和`@task`装饰器实现。  

1.  **定义工作流：**  
    *   主流程（如`med-rag-flow/main_flow.py`中的`process_documents_flow`）负责协调任务。  
    *   任务可能包括：`scan_for_new_pdfs`、`parse_pdf`、`chunk_text`、`generate_embeddings`、`save_to_vector_store`、`update_backend_status`。  
2.  **注册并运行工作流（Prefect 2.x）：**  
    *   **直接运行包含工作流的Python脚本：**  
        ```bash  
        python med-rag-flow/main_flow.py  
        ```  
        （假设脚本末尾直接调用流程函数以执行）。  
    *   **使用Prefect CLI进行高级部署：**  
        *   创建工作流部署：  
            ```bash  
            prefect deployment build ./main_flow.py:process_documents_flow -n pdf-processing-deployment -q default  
            ```  
        *   应用部署配置：  
            ```bash  
            prefect deployment apply process_documents_flow-deployment.yaml  
            ```  
        *   启动代理以处理“default”工作队列的任务：  
            ```bash  
            prefect agent start -q default  
            ```  
        *   随后可通过Prefect UI或CLI触发流程运行：  
            ```bash  
            prefect deployment run process_documents_flow/pdf-processing-deployment  
            ```  
3.  **监控：**  
    *   若使用Prefect服务（本地或云端），可通过Prefect UI监控流程运行状态。  
    *   日志通常输出至控制台和/或由Prefect存储。  

具体运行命令取决于`med-rag-flow`目录中Prefect工作流的部署结构。

---