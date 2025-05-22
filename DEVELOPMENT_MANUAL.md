# Development Manual

## Table of Contents

1.  [Introduction](#introduction)
    1.1. [Project Overview](#project-overview)
    1.2. [Directory Structure](#directory-structure)
2.  [Backend Development (`server/`)](#backend-development-server)
    2.1. [Setup and Installation](#backend-setup-and-installation)
    2.2. [Running Backend Development Server](#running-backend-development-server)
    2.3. [Configuration](#backend-configuration)
    2.4. [Database](#backend-database)
        2.4.1. [Database Models](#database-models)
        2.4.2. [Data Access Objects (DAOs)](#data-access-objects-daos)
    2.5. [API Endpoints](#backend-api-endpoints)
        2.5.1. [API Schemas](#backend-api-schemas)
        2.5.2. [Knowledge Base API (`/knowledge-bases`)](#knowledge-base-api-knowledge-bases)
        2.5.3. [Document API (`/document`)](#document-api-document)
    2.6. [Testing Backend](#testing-backend)
    2.7. [Pre-commit Hooks](#backend-pre-commit-hooks)
3.  [Frontend Development (`frontend/`)](#frontend-development-frontend)
    3.1. [Setup and Installation](#frontend-setup-and-installation)
    3.2. [Running Frontend Development Server](#running-frontend-development-server)
    3.3. [Routing](#frontend-routing)
    3.4. [Pages](#frontend-pages)
        3.4.1. [`index2.vue` (Chat Interface)](#index2vue-chat-interface)
        3.4.2. [Other Pages](#other-frontend-pages)
    3.5. [API Services](#frontend-api-services)
        3.5.1. [HTTP Client Setup (`client.ts`)](#http-client-setup-clientts)
        3.5.2. [Medical RAG Service (`medicalRag.ts`)](#medical-rag-service-medicalragts)
        3.5.3. [Knowledge Base Service (`knowledgeBase.ts`)](#knowledge-base-service-knowledgebasets)
        3.5.4. [Document Service (`document.ts`)](#document-service-documentts)
    3.6. [State Management (Pinia)](#frontend-state-management-pinia)
        3.6.1. [Pinia Setup (`stores/index.ts`)](#pinia-setup-storesindexts)
        3.6.2. [Auth Store (`stores/auth.store.ts`)](#auth-store-storesauthstorets)
4.  [Workflow Engine (`med-rag-flow/`)](#workflow-engine-med-rag-flow)
    4.1. [Overview](#workflow-overview)
    4.2. [Setup](#workflow-setup)
    4.3. [Running Workflows](#running-workflows)

---

## 1. Introduction

### 1.1. Project Overview
This project is a medical RAG (Retrieval Augmented Generation) system with a web interface. It consists of three main parts:
- A **backend server** built with FastAPI, responsible for API logic, database interactions, and coordinating with the RAG pipeline.
- A **frontend application** built with Vue.js (using Bun and Vite), providing the user interface for chat, knowledge base management, and document handling.
- A **workflow engine** (`med-rag-flow`) using Python and Prefect, designed for batch processing of PDF documents, including parsing, chunking, vector generation, and integration with the backend.

### 1.2. Directory Structure
The project root contains the following main directories:
- `frontend/`: Contains the Vue.js frontend application.
- `server/`: Contains the FastAPI backend application.
- `med-rag-flow/`: Contains the Python-based data processing pipeline using Prefect.
- `README.md`, `README_FRONTEND.md`, `README_SERVER.md`, `README_WORKFLOW.md`: Provide specific details for each part of the project.

---

## 2. Backend Development (`server/`)

### 2.1. Backend Setup and Installation
The backend is a FastAPI application managed with Poetry.

**Prerequisites:**
*   Python 3.9+
*   Poetry (Python dependency manager)
*   Docker (for database and other services)

**Steps:**
1.  **Navigate to the server directory:**
    ```bash
    cd server/
    ```
2.  **Install dependencies using Poetry:**
    ```bash
    poetry install
    ```
3.  **Environment Configuration (`.env` file):**
    *   Copy the example environment file:
        ```bash
        cp .env.example .env
        ```
    *   Modify the `.env` file with your specific configurations, especially database connection strings, API keys, and other sensitive information. Key variables include:
        *   `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASS`, `DB_NAME`
        *   `RAG_API_URL`, `RAG_API_KEY` (if applicable)
        *   `JWT_SECRET_KEY`, `JWT_ALGORITHM`
        *   `CORS_ORIGINS` (comma-separated list of allowed frontend origins)
        *   Paths for file storage/uploads if not using cloud storage.
4.  **Database Setup (Docker):**
    *   The project uses Docker Compose to manage services like PostgreSQL.
    *   Ensure Docker is running.
    *   Start the database service (and any other defined services):
        ```bash
        docker-compose up -d db 
        ```
        (Or `docker-compose up -d` to start all services defined in `docker-compose.yml`)
    *   Run Alembic migrations to set up the database schema:
        ```bash
        poetry run alembic upgrade head
        ```
5.  **Pre-commit Hooks:**
    *   The project uses pre-commit hooks for code linting and formatting (e.g., Black, Flake8, isort, MyPy).
    *   Install the hooks:
        ```bash
        poetry run pre-commit install
        ```
    *   These hooks will run automatically before each commit.

### 2.2. Running Backend Development Server
1.  **Ensure the database is running** (as described in setup).
2.  **Navigate to the `server/` directory.**
3.  **Run the FastAPI development server using Uvicorn (via Poetry):**
    ```bash
    poetry run uvicorn med_rag_server.web.application:get_app --reload --host 0.0.0.0 --port 8000
    ```
    *   `--reload`: Enables auto-reloading when code changes.
    *   `--host 0.0.0.0`: Makes the server accessible from outside the Docker container/machine (e.g., from your host machine or other devices on the network).
    *   `--port 8000`: Specifies the port to run on.
4.  The API will be accessible at `http://localhost:8000` (or the configured host/port). The OpenAPI documentation (Swagger UI) will be available at `http://localhost:8000/api/docs` and ReDoc at `http://localhost:8000/api/redoc`.

### 2.3. Backend Configuration
Backend configuration is primarily managed through:
1.  **Environment Variables (`.env` file):**
    *   Located in `server/.env`.
    *   Created from `server/.env.example`.
    *   Loaded at runtime by the FastAPI application (e.g., using Pydantic's Settings management).
    *   Contains sensitive information like database credentials, API keys, JWT secrets, CORS origins, and external service URLs.
    *   Example variables: `DB_HOST`, `DB_USER`, `DB_PASS`, `DB_NAME`, `JWT_SECRET_KEY`, `RAG_API_URL`, `LOG_LEVEL`.
2.  **Application Settings (`server/med_rag_server/settings.py`):**
    *   Often uses Pydantic's `BaseSettings` to load and validate environment variables.
    *   Provides a structured way to access configuration values throughout the application.
    *   May define default values if corresponding environment variables are not set.
3.  **Poetry Configuration (`pyproject.toml`):**
    *   Located in `server/pyproject.toml`.
    *   Defines project dependencies, Python version, and tool configurations (like Black, isort, MyPy).
4.  **Logging Configuration (`server/med_rag_server/web/application.py` or separate module):**
    *   Typically configured within the FastAPI application setup.
    *   May use Python's built-in `logging` module.
    *   Log level can often be set via an environment variable (e.g., `LOG_LEVEL`).
5.  **Alembic Configuration (`server/alembic.ini`):**
    *   Configures database migration settings for Alembic.
    *   Includes the database URL, which Alembic uses to connect to the database. This is often sourced from an environment variable.

### 2.4. Backend Database
The backend uses a SQL database, typically PostgreSQL, managed via SQLAlchemy ORM and Alembic for migrations.

#### 2.4.1. Database Models
Located in `server/med_rag_server/db/models/`. These are SQLAlchemy declarative models representing database tables.

*   **`KnowledgeBaseModel` (`knowledge_base_model.py`):**
    *   Represents a knowledge base, which is a collection of documents.
    *   **Key Fields:**
        *   `id` (Integer, Primary Key): Unique identifier for the knowledge base.
        *   `name` (String, Not Nullable, Unique): User-defined name for the knowledge base.
        *   `description` (Text, Nullable): Optional description.
        *   `created_at` (DateTime, Not Nullable, Default: now): Timestamp of creation.
        *   `updated_at` (DateTime, Not Nullable, Default: now, On Update: now): Timestamp of last update.
        *   `documents` (Relationship): One-to-many relationship with `DocumentModel`. A knowledge base can have multiple documents.
        *   `vector_storage_path` (String, Nullable): Filesystem or object storage path for the vector embeddings associated with this KB.
        *   `processing_status` (String, Nullable, Default: "pending"): Indicates the status of document processing for this KB (e.g., "pending", "processing", "completed", "failed").

*   **`DocumentModel` (`document_model.py`):**
    *   Represents an individual document within a knowledge base.
    *   **Key Fields:**
        *   `id` (Integer, Primary Key): Unique identifier for the document.
        *   `name` (String, Not Nullable): Name of the document (e.g., filename).
        *   `kb_id` (Integer, Foreign Key to `knowledge_bases.id`, Not Nullable): ID of the knowledge base this document belongs to.
        *   `file_path` (String, Not Nullable): Path to the original document file.
        *   `file_type` (String, Nullable): Mimetype or extension of the file (e.g., "application/pdf", "text/plain").
        *   `status` (String, Nullable, Default: "pending"): Processing status of the document (e.g., "pending", "processing", "completed", "failed").
        *   `created_at` (DateTime, Not Nullable, Default: now): Timestamp of creation.
        *   `updated_at` (DateTime, Not Nullable, Default: now, On Update: now): Timestamp of last update.
        *   `knowledge_base` (Relationship): Many-to-one relationship back to `KnowledgeBaseModel`.
        *   `metadata_` (JSON, Nullable): Stores additional metadata about the document (e.g., author, number of pages, custom tags). Stored as `metadata_` to avoid conflict with SQLAlchemy's `metadata` attribute.

*   **`DummyModel` (`dummy_model.py`):**
    *   A placeholder or example model.
    *   **Key Fields:**
        *   `id` (Integer, Primary Key): Unique identifier.
        *   `name` (String, Nullable, Unique): Name for the dummy entry.
        *   `created_at` (DateTime, Default: now): Timestamp of creation.

#### 2.4.2. Data Access Objects (DAOs)
Located in `server/med_rag_server/db/dao/`. DAOs encapsulate the logic for interacting with the database models, providing a CRUD (Create, Read, Update, Delete) interface.

*   **`KnowledgeBaseDAO` (`knowledge_base_dao.py`):**
    *   Provides methods for interacting with the `KnowledgeBaseModel` table.
    *   **Key Methods:**
        *   `create_knowledge_base_model(name: str, description: Optional[str] = None, vector_storage_path: Optional[str] = None, processing_status: Optional[str] = "pending") -> KnowledgeBaseModel`: Creates a new knowledge base.
        *   `get_knowledge_base_model(kb_id: int) -> Optional[KnowledgeBaseModel]`: Retrieves a knowledge base by its ID.
        *   `get_knowledge_base_model_by_name(name: str) -> Optional[KnowledgeBaseModel]`: Retrieves a knowledge base by its name.
        *   `get_all_knowledge_base_models(limit: int = 10, offset: int = 0) -> List[KnowledgeBaseModel]`: Retrieves a paginated list of all knowledge bases.
        *   `update_knowledge_base_model(kb_id: int, name: Optional[str] = None, description: Optional[str] = None, vector_storage_path: Optional[str] = None, processing_status: Optional[str] = None) -> Optional[KnowledgeBaseModel]`: Updates an existing knowledge base.
        *   `delete_knowledge_base_model(kb_id: int) -> bool`: Deletes a knowledge base by its ID.

*   **`DocumentDAO` (`document_dao.py`):**
    *   Provides methods for interacting with the `DocumentModel` table.
    *   **Key Methods:**
        *   `create_document_model(name: str, kb_id: int, file_path: str, file_type: Optional[str] = None, status: Optional[str] = "pending", metadata_: Optional[dict] = None) -> DocumentModel`: Creates a new document.
        *   `get_document_model(doc_id: int) -> Optional[DocumentModel]`: Retrieves a document by its ID.
        *   `get_documents_by_kb_id(kb_id: int, limit: int = 10, offset: int = 0) -> List[DocumentModel]`: Retrieves all documents belonging to a specific knowledge base.
        *   `update_document_model(doc_id: int, name: Optional[str] = None, status: Optional[str] = None, metadata_: Optional[dict] = None) -> Optional[DocumentModel]`: Updates an existing document.
        *   `delete_document_model(doc_id: int) -> bool`: Deletes a document by its ID.
        *   `delete_documents_by_kb_id(kb_id: int) -> int`: Deletes all documents associated with a given knowledge base ID and returns the count of deleted documents.

*   **`DummyDAO` (`dummy_dao.py`):**
    *   Provides methods for interacting with the `DummyModel` table.
    *   **Key Methods:**
        *   `create_dummy_model(name: str) -> None`: Creates a new dummy model instance.
        *   `get_all_dummy_models(limit: int = 10, offset: int = 0) -> List[DummyModel]`: Retrieves all dummy models with pagination.
        *   `get_dummy_model(dummy_id: int) -> Optional[DummyModel]`: Retrieves a specific dummy model by its ID.

### 2.5. Backend API Endpoints
Defined in `server/med_rag_server/web/api/`. These modules contain the FastAPI routers and endpoint logic.

#### 2.5.1. Backend API Schemas
Located in `server/med_rag_server/web/api/schemas/`. These are Pydantic models used for request and response validation, serialization, and documentation.

*   **Knowledge Base Schemas (`knowledge_base.py`):**
    *   `KnowledgeBaseBase` (Pydantic BaseModel): Base schema with common fields.
        *   `name`: str
        *   `description`: Optional[str] = None
        *   `vector_storage_path`: Optional[str] = None
        *   `processing_status`: Optional[str] = "pending"
    *   `KnowledgeBaseCreate` (Inherits from `KnowledgeBaseBase`): Schema for creating a new knowledge base.
    *   `KnowledgeBaseUpdate` (Inherits from `KnowledgeBaseBase`): Schema for updating an existing knowledge base. Fields are optional.
    *   `KnowledgeBaseInDB` (Inherits from `KnowledgeBaseBase`): Schema for data stored in the database, includes `id`.
        *   `id`: int
    *   `KnowledgeBaseResponse` (Inherits from `KnowledgeBaseInDB`): Schema for API responses, typically includes fields like `id`, `name`, `description`, `created_at`, `updated_at`, `processing_status`.
        *   `created_at`: datetime
        *   `updated_at`: datetime
    *   `KnowledgeBaseListResponse` (Pydantic BaseModel): Schema for a list of knowledge bases, often including pagination details.
        *   `data`: List[KnowledgeBaseResponse]
        *   `total`: int

*   **Document Schemas (`document.py`):**
    *   `DocumentBase` (Pydantic BaseModel): Base schema with common document fields.
        *   `name`: str
        *   `file_type`: Optional[str] = None
        *   `status`: Optional[str] = "pending"
        *   `metadata_`: Optional[dict] = None
    *   `DocumentCreate` (Inherits from `DocumentBase`): Schema for creating a new document (used when uploading a document to a KB).
        *   `kb_id`: int (implicitly, as documents are usually created in context of a KB)
        *   `file_path`: str (internal, usually not directly in request from client for creation)
    *   `DocumentUpdate` (Inherits from `DocumentBase`): Schema for updating document metadata. Fields are optional.
    *   `DocumentInDB` (Inherits from `DocumentBase`): Schema for document data in DB.
        *   `id`: int
        *   `kb_id`: int
        *   `file_path`: str
    *   `DocumentResponse` (Inherits from `DocumentInDB`): Schema for API responses for a single document.
        *   `created_at`: datetime
        *   `updated_at`: datetime
    *   `DocumentListResponse` (Pydantic BaseModel): Schema for a list of documents.
        *   `data`: List[DocumentResponse]
        *   `total`: int
    *   `MedicalRagQuery` (Pydantic BaseModel): Schema for querying the medical RAG system.
        *   `question`: str
        *   `kb_id`: int (ID of the knowledge base to query)
        *   `language`: Optional[Literal['zh', 'en']] = 'zh'
        *   `require_references`: Optional[bool] = True
        *   `safety_warnings`: Optional[bool] = True
    *   `Reference` (Pydantic BaseModel): Schema for a reference source in RAG response.
        *   `text`: str
        *   `source`: str
    *   `MedicalRagResponseMetadata` (Pydantic BaseModel): Metadata for RAG response.
        *   `doc_count`: int
        *   `kb_id`: int
        *   `vector_path`: Optional[str]
    *   `MedicalRagResponse` (Pydantic BaseModel): Schema for the full RAG response.
        *   `answer`: str
        *   `references`: List[Reference]
        *   `metadata`: MedicalRagResponseMetadata

#### 2.5.2. Knowledge Base API (`/knowledge-bases`)
Router prefix: `/api/knowledge-bases`. Handled by `server/med_rag_server/web/api/knowledge_base/views.py`.

*   **`POST /`**: Create a new knowledge base.
    *   Request Body: `KnowledgeBaseCreate` schema.
    *   Response: `KnowledgeBaseResponse` schema.
    *   Summary: Takes KB name and optional description. Returns the created KB object.
*   **`GET /`**: List all knowledge bases with pagination.
    *   Query Parameters: `limit` (int, default 10), `offset` (int, default 0).
    *   Response: `KnowledgeBaseListResponse` schema (containing a list of `KnowledgeBaseResponse`).
    *   Summary: Retrieves a paginated list of knowledge bases.
*   **`GET /{kb_id}`**: Get a specific knowledge base by ID.
    *   Path Parameter: `kb_id` (int).
    *   Response: `KnowledgeBaseResponse` schema.
    *   Summary: Retrieves details of a single KB.
*   **`PUT /{kb_id}`**: Update a knowledge base.
    *   Path Parameter: `kb_id` (int).
    *   Request Body: `KnowledgeBaseUpdate` schema.
    *   Response: `KnowledgeBaseResponse` schema.
    *   Summary: Updates name, description, or other mutable fields of a KB.
*   **`DELETE /{kb_id}`**: Delete a knowledge base.
    *   Path Parameter: `kb_id` (int).
    *   Response: Status code 204 (No Content) on success or an error message.
    *   Summary: Deletes a KB and potentially its associated documents and vector data (implementation dependent).
*   **`POST /{kb_id}/upload-document`**: Upload a document to a specific knowledge base.
    *   Path Parameter: `kb_id` (int).
    *   Request: `UploadFile` (FastAPI's file upload type).
    *   Response: `DocumentResponse` schema for the created document record.
    *   Summary: Uploads a file, saves it, creates a document record in the DB, and potentially triggers a processing workflow.
*   **`GET /{kb_id}/documents`**: List documents within a specific knowledge base.
    *   Path Parameter: `kb_id` (int).
    *   Query Parameters: `limit` (int, default 10), `offset` (int, default 0).
    *   Response: `DocumentListResponse` schema.
    *   Summary: Retrieves a paginated list of documents for a given KB.

#### 2.5.3. Document API (`/document`)
Router prefix: `/api/document`. Handled by `server/med_rag_server/web/api/document/views.py`.

*   **`GET /{doc_id}`**: Get a specific document by ID.
    *   Path Parameter: `doc_id` (int).
    *   Response: `DocumentResponse` schema.
    *   Summary: Retrieves details of a single document.
*   **`PUT /{doc_id}`**: Update document metadata.
    *   Path Parameter: `doc_id` (int).
    *   Request Body: `DocumentUpdate` schema.
    *   Response: `DocumentResponse` schema.
    *   Summary: Updates mutable fields of a document, like its name or status.
*   **`DELETE /{doc_id}`**: Delete a document.
    *   Path Parameter: `doc_id` (int).
    *   Response: Status code 204 (No Content) on success or an error message.
    *   Summary: Deletes a document record and its associated file.
*   **`POST /medical-search-stream`**: Perform a medical RAG query with streaming response.
    *   Request Body: `MedicalRagQuery` schema.
    *   Response: `StreamingResponse` (Server-Sent Events).
        *   Events:
            *   `event: data, data: {"delta": "text chunk"}` (for streaming answer)
            *   `event: references, data: {"sources": ["source1", "source2"]}` (for references)
            *   `event: complete, data: {"metadata": {"doc_count": N, "kb_id": X, ...}}` (signals end of stream with metadata)
            *   `event: error, data: {"error": "message"}` (if an error occurs)
    *   Summary: Takes a question and KB ID, streams back the RAG answer, references, and metadata.

### 2.6. Testing Backend
*   **Framework:** Pytest is commonly used for testing FastAPI applications.
*   **Location:** Tests are typically located in the `server/tests/` directory.
*   **Structure:**
    *   `tests/api/`: Integration tests for API endpoints.
    *   `tests/db/`: Unit tests for database DAOs and models.
    *   `tests/services/`: Unit tests for business logic/services.
    *   `tests/conftest.py`: Contains fixtures for tests (e.g., test database setup, API client).
*   **Running Tests:**
    ```bash
    poetry run pytest
    ```
    Or, to run with coverage:
    ```bash
    poetry run pytest --cov=med_rag_server
    ```
*   **Key Aspects Tested:**
    *   API endpoint responses (status codes, JSON structure, data correctness).
    *   Authentication and authorization logic.
    *   Database interactions (CRUD operations in DAOs).
    *   Business logic in services.
    *   Error handling.
*   **Test Database:** Tests often use a separate test database (e.g., a temporary SQLite DB or a dedicated PostgreSQL test DB) to avoid interfering with the development database. Fixtures in `conftest.py` manage the setup and teardown of this test database and provide a test client for making API requests.

### 2.7. Backend Pre-commit Hooks
*   **Purpose:** To automate code quality checks (linting, formatting, type checking) before commits are made.
*   **Configuration:** Defined in `server/.pre-commit-config.yaml`.
*   **Common Hooks Used:**
    *   **Black:** For opinionated code formatting.
    *   **Flake8:** For style guide enforcement (PEP 8) and error detection.
    *   **isort:** For sorting imports automatically.
    *   **MyPy:** For static type checking.
    *   **Prettier:** (If applicable, for JSON, YAML, MD files).
    *   Hooks for detecting large files, trailing whitespace, etc.
*   **Installation:**
    ```bash
    poetry run pre-commit install
    ```
    This installs the hooks into your local Git repository. They will run automatically when you attempt to commit changes. If a hook fails, the commit will be aborted, allowing you to fix the issues.
*   **Manual Execution:**
    You can run all pre-commit hooks manually on all files:
    ```bash
    poetry run pre-commit run --all-files
    ```

---

## 3. Frontend Development (`frontend/`)

### 3.1. Frontend Setup and Installation
The frontend is a Vue.js application, likely using Vite for building and Bun as the JavaScript runtime/package manager.

**Prerequisites:**
*   Bun (JavaScript runtime and toolkit)
*   Node.js and npm (primarily for PM2 if used for process management in production/staging)

**Steps:**
1.  **Navigate to the frontend directory:**
    ```bash
    cd frontend/
    ```
2.  **Install dependencies using Bun:**
    ```bash
    bun install
    ```
3.  **Environment Configuration (`.env` files):**
    *   Vue.js projects (especially with Vite) use `.env` files for environment variables (e.g., `.env`, `.env.development`, `.env.production`).
    *   Common variables:
        *   `VITE_BASE_URL`: The base URL for the backend API (e.g., `http://localhost:8000/api`).
        *   Other API keys or configuration flags for the frontend.
    *   Create `.env.local` or `.env.development.local` for local overrides if needed (these are usually gitignored). Example:
        ```
        VITE_BASE_URL=http://localhost:8000/api 
        ```
        (Note: Vite requires variables exposed to the client to be prefixed with `VITE_`)

### 3.2. Running Frontend Development Server
1.  **Navigate to the `frontend/` directory.**
2.  **Run the development server using Bun:**
    ```bash
    bun run dev
    ```
    This command typically starts the Vite development server.
3.  The frontend application will usually be accessible at `http://localhost:5173` (Vite's default port, but can vary). The console output will indicate the correct URL.

**Alternative for Production/Staging (using PM2):**
If PM2 (a Node.js process manager) is used:
1.  **Ensure Node.js and npm are installed.**
2.  **Install PM2 globally:**
    ```bash
    npm install pm2 -g
    ```
3.  **Build the frontend application for production:**
    ```bash
    bun run build
    ```
    This creates a `dist/` directory with optimized static assets.
4.  **Serve the built application using a static server (e.g., `serve`) or configure PM2 to serve it.**
    If using a simple Node.js server for the built assets, you might have an `ecosystem.config.js` for PM2:
    ```javascript
    // ecosystem.config.js
    module.exports = {
      apps : [{
        name   : "frontend-app",
        script : "npm", // or path to a server script like server.js
        args   : "run start:prod", // if you have a specific prod start script
        // or if serving static files with a simple server:
        // script : "npx",
        // args   : "serve -s dist -l 3000", 
        cwd    : "./frontend", // current working directory
        watch  : false,
        env_production: {
           NODE_ENV: "production",
           PORT: 3000 // Example port
        }
      }]
    }
    ```
    Then run with PM2:
    ```bash
    pm2 start ecosystem.config.js --env production
    ```

### 3.3. Frontend Routing
Routing is managed by `vue-router`. The main configuration is typically in `frontend/src/router/index.ts`.

*   **Router Setup (`frontend/src/router/index.ts`):**
    *   Imports `createRouter`, `createWebHistory` (or `createWebHashHistory`) from `vue-router`.
    *   Defines an array of `RouteRecordRaw` objects.
    *   Initializes the router instance:
        ```typescript
        import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
        import HomeView from '../views/HomeView.vue' // Example import

        const routes: Array<RouteRecordRaw> = [
          // ... route definitions
        ]

        const router = createRouter({
          history: createWebHistory(import.meta.env.BASE_URL), // BASE_URL often from Vite config
          routes
        })

        export default router
        ```
    *   This router instance is then used in `main.ts` (`app.use(router)`).

*   **Navigation Guards/Middlewares:**
    *   Global navigation guards (e.g., `router.beforeEach`) can be defined in `router/index.ts` or a separate middleware file.
    *   These are used for tasks like authentication checks (redirecting to login if not authenticated), setting breadcrumbs, or analytics.
    *   Example:
        ```typescript
        import { useAuthStore } from '@/stores/auth.store' // Assuming Pinia store

        router.beforeEach(async (to, from, next) => {
          const authStore = useAuthStore()
          const requiresAuth = to.meta.requiresAuth ?? false
          const publicPages = ['/login', '/register'] // Example public pages

          if (requiresAuth && !authStore.isAuthenticated) {
            if (!publicPages.includes(to.path)) {
              return next({ path: '/login', query: { redirect: to.fullPath } })
            }
          }
          // Potentially fetch user if token exists but user data not loaded
          // if (authStore.token && !authStore.user) {
          //   await authStore.fetchUser();
          // }
          next()
        })
        ```
    *   Per-route navigation guards (`beforeEnter`) can also be defined within specific route records.

*   **Route Definitions Table:**
    The `routes` array contains objects, each defining a route:
    | Path                | Name         | Component (View)     | `meta` (example)                  | Lazy Loaded? |
    | ------------------- | ------------ | -------------------- | --------------------------------- | ------------ |
    | `/`                 | `Home`       | `HomeView.vue`       | `{ requiresAuth: true }`          | No (example) |
    | `/login`            | `Login`      | `LoginView.vue`      |                                   | Yes          |
    | `/register`         | `Register`   | `RegisterView.vue`   |                                   | Yes          |
    | `/chat`             | `Chat`       | `Index2View.vue`     | `{ requiresAuth: true }`          | Yes          |
    | `/kb`               | `KBList`     | `KbListView.vue`     | `{ requiresAuth: true }`          | Yes          |
    | `/kb/create`        | `KBCreate`   | `KbCreateView.vue`   | `{ requiresAuth: true }`          | Yes          |
    | `/kb/:id`           | `KBDetail`   | `KbDetailView.vue`   | `{ requiresAuth: true, props:true}`| Yes          |
    | `/kb/:id/upload`    | `KBUpload`   | `KbUploadView.vue`   | `{ requiresAuth: true, props:true}`| Yes          |
    | `/documents`        | `DocList`    | `DocListView.vue`    | `{ requiresAuth: true }`          | Yes          |
    | `/documents/:id`    | `DocDetail`  | `DocDetailView.vue`  | `{ requiresAuth: true, props:true}`| Yes          |
    | `/settings`         | `Settings`   | `SettingsView.vue`   | `{ requiresAuth: true }`          | Yes          |
    | `/:pathMatch(.*)*` | `NotFound`   | `NotFoundView.vue`   |                                   | Yes          |

    *Lazy Loading Example for a route:*
    ```typescript
    {
      path: '/chat',
      name: 'Chat',
      component: () => import('@/pages/index2.vue'), // Lazy load
      meta: { requiresAuth: true }
    }
    ```

### 3.4. Frontend Pages
Located in `frontend/src/pages/` or `frontend/src/views/`. These are the main Vue components rendered by `vue-router`.

#### 3.4.1. `index2.vue` (Chat Interface)
File: `frontend/src/pages/index2.vue`

This is the primary user interface for interacting with the RAG system.

*   **Layout:**
    *   Uses `ResizablePanelGroup` for a multi-panel layout.
    *   **Left Panel:** Displays conversation history.
        *   Lists past conversations with titles and timestamps.
        *   Allows selecting a conversation to view its messages.
        *   "New Chat" button to start a new conversation.
    *   **Right Panel (Main Area):**
        *   **Chat Content Area:** Displays messages of the active conversation.
            *   User messages are typically right-aligned.
            *   Assistant messages are left-aligned and include:
                *   Avatar.
                *   Tabs for "Reply Content", "Document Citation", and "Original Image" (if applicable).
                *   **Reply Content Tab:** Shows the Markdown rendered RAG response (using `v-md-preview`).
                *   **Document Citation Tab:** Displays references used by the RAG model. Each reference shows the source and optionally text snippets.
                *   Timestamp for each message.
        *   **Input Area:**
            *   Textarea for user input with Shift+Enter for new lines.
            *   Knowledge base selection dropdown (`Select` component).
            *   Action buttons (e.g., Attach file, Sparkles, Settings).
            *   "Send" button (with loading state: spinner and "Sending..." text).

*   **Key Script Logic (`<script setup lang="ts">`):**
    *   **State Management:**
        *   `conversations`: `ref<Conversation[]>` storing all conversation threads.
        *   `activeIndex`: `ref<number>` for the currently selected conversation.
        *   `inputMessage`: `ref<string>` for the user's current message in the textarea.
        *   `selectedKbId`: `ref<number>` for the chosen knowledge base.
        *   `knowledgeBases`: `ref<KnowledgeBase[]>` list of available KBs.
        *   `isLoading`: `ref<boolean>` to manage the loading state during API calls.
    *   **Computed Properties:**
        *   `activeMessages`: Computed from `conversations` and `activeIndex` to get messages for the current chat.
    *   **API Calls:**
        *   `sendMessage()`:
            *   Sets `isLoading` to true.
            *   Constructs user message and adds it to `activeMessages`.
            *   Creates a reactive `assistantMessage` object.
            *   Calls `apiMedicalRag.streamQuery()` from `medicalRag.ts`.
            *   Handles streaming data (`onData`): appends deltas to `assistantMessage.content`.
            *   Handles completion (`onComplete`): sets final content and references, sets `isLoading` to false.
            *   Handles errors (`onError`): displays error, sets `isLoading` to false.
        *   Fetches knowledge bases on component mount (`onMounted`) using `apiKnowledgeBase.getList()`.
    *   **Component Interaction:**
        *   `newConversation()`: Creates a new, empty conversation object and sets it as active.
        *   `selectConversation()`: Changes `activeIndex`.
        *   `handleKeydown()`: Manages Enter/Shift+Enter in the textarea.
        *   `smartScroll()`: Auto-scrolls the chat area to the latest message.
    *   **Utility Functions:**
        *   `formatDate()`, `formatTime()` for display.
    *   **Markdown Rendering:** Uses `@kangc/v-md-editor` for rendering assistant's Markdown responses.

#### 3.4.2. Other Frontend Pages
Brief descriptions of other Vue components that function as pages:

*   **`LoginView.vue` / `RegisterView.vue`:** Standard authentication pages with forms for user login and registration. They interact with authentication API endpoints (likely via `auth.store.ts` or a dedicated auth API service).
*   **`HomeView.vue`:** Could be a dashboard, landing page after login, or a redirector.
*   **Knowledge Base Management Pages:**
    *   **`KbListView.vue` (`/kb`):** Displays a list of available knowledge bases with options to view details, edit, or delete. Likely fetches data using `knowledgeBase.ts` API service. May show KB name, description, status, number of documents.
    *   **`KbCreateView.vue` (`/kb/create`):** A form to create a new knowledge base (name, description). Submits data via `knowledgeBase.ts`.
    *   **`KbDetailView.vue` (`/kb/:id`):** Shows details of a specific knowledge base, including a list of its documents, status, and options to upload new documents or trigger reprocessing.
    *   **`KbUploadView.vue` (`/kb/:id/upload`):** Provides an interface (e.g., file dropzone) to upload documents to a specific knowledge base. Interacts with the document upload API endpoint.
*   **Document Management Pages (Optional, if separate from KB views):**
    *   **`DocListView.vue` (`/documents`):** Might list all documents across all KBs or allow filtering.
    *   **`DocDetailView.vue` (`/documents/:id`):** Shows details of a specific document, its content (if viewable), metadata, and status.
*   **`SettingsView.vue` (`/settings`):** Page for user profile settings, application preferences, etc.
*   **`NotFoundView.vue` (`/:pathMatch(.*)*`):** A generic "404 Not Found" page.

### 3.5. Frontend API Services
Located in `frontend/src/api/`. These TypeScript modules encapsulate logic for making HTTP requests to the backend.

#### 3.5.1. HTTP Client Setup (`client.ts`)
File: `frontend/src/api/client.ts`

*   **Purpose:** Configures and exports an Axios instance for making HTTP requests.
*   **Key Features:**
    *   **Base URL:** Sets the `baseURL` for all requests, typically from `import.meta.env.VITE_BASE_URL`.
    *   **Headers:** Default headers (e.g., `Content-Type: application/json`).
    *   **Interceptors:**
        *   **Request Interceptor:** Adds the JWT token (from Pinia store or localStorage) to the `Authorization` header of outgoing requests if the user is authenticated.
        *   **Response Interceptor:** Handles global error responses (e.g., 401 Unauthorized for redirecting to login, 403 Forbidden, 500 Internal Server Error for generic error messages). Can also be used for response data transformation.
    *   **Timeout:** Default request timeout.
*   **Example Structure:**
    ```typescript
    import axios, { type AxiosInstance, type InternalAxiosRequestConfig, type AxiosResponse } from 'axios'
    import { useAuthStore } from '@/stores/auth.store' // Assuming Pinia store

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
      (response: AxiosResponse) => response, // Or response.data if you prefer to always get data
      async (error) => {
        const authStore = useAuthStore()
        if (error.response?.status === 401) {
          authStore.logout() // Or attempt token refresh
          // Potentially redirect to login: router.push('/login')
        }
        return Promise.reject(error)
      }
    )

    export default apiClient
    ```

#### 3.5.2. Medical RAG Service (`medicalRag.ts`)
File: `frontend/src/api/medicalRag.ts`

*   **Purpose:** Handles API calls related to the medical RAG functionality, especially the streaming chat query.
*   **Key Interfaces/Types:**
    *   `MedicalRagQuery`: Defines the structure for the query payload (question, kb_id, language, etc.). Matches backend Pydantic schema.
    *   `Reference`: Defines the structure for a reference object (`{ text: string, source: string }`).
    *   `MedicalRagResponseMetadata`: For metadata in the RAG response.
*   **`SSEParser` Class:**
    *   A utility class to parse Server-Sent Events (SSE) streams.
    *   `constructor(config: { onMessage: (event: MessageEvent) => void, onError: (error: string) => void })`
    *   `feed(chunk: string)`: Processes incoming chunks of data from the stream, buffers them, and extracts full SSE messages (event type and data).
    *   `processBuffer()`: Internal method to parse complete events from the buffer.
*   **`apiMedicalRag.streamQuery()` Method:**
    *   `async streamQuery(payload: MedicalRagQuery, handlers: { onData, onComplete, onError })`
    *   Uses the `fetch` API to make a POST request to the backend's `/document/medical-search-stream` endpoint.
    *   Handles the streaming response:
        *   Gets a `ReadableStreamDefaultReader` from `response.body`.
        *   Reads chunks from the stream (`reader.read()`).
        *   Decodes chunks (`TextDecoder`) and feeds them to an `SSEParser` instance.
    *   The `SSEParser` then calls the provided `handlers`:
        *   `onData(delta: string)`: Called for `event: data` (streaming answer).
        *   `onComplete({ references: Reference[], ...metadata })`: Called for `event: complete`. This service transforms the `event: references` (with `{"sources":[]}`) and `event: complete` (with metadata) from the backend into a single `onComplete` call with the correct `Reference[]` structure.
        *   `onError(error: string)`: Called for `event: error` or other stream/parsing errors.
*   **Transformation Logic:**
    *   Initializes `let collectedReferences: Reference[] = []`.
    *   When an SSE `event: references` with `data: {"sources": ["s1", "s2"]}` is received, it maps `data.sources` to `[{source: "s1", text: "s1"}, {source: "s2", text: "s2"}]` and stores it in `collectedReferences`.
    *   When the SSE `event: complete` is received (which contains metadata but not the references themselves as per the design), the `handlers.onComplete` is invoked with the `collectedReferences` and the metadata from the `complete` event.

#### 3.5.3. Knowledge Base Service (`knowledgeBase.ts`)
File: `frontend/src/api/knowledgeBase.ts`

*   **Purpose:** Handles CRUD operations for knowledge bases.
*   **Uses:** `apiClient` (the configured Axios instance).
*   **Key Interfaces/Types:**
    *   `KnowledgeBase` (or `KnowledgeBaseResponse` from backend schemas): For the structure of a KB object.
    *   `KnowledgeBaseCreate`, `KnowledgeBaseUpdate`: For request payloads.
*   **Key Methods:**
    *   `getList(params: { limit?: number, offset?: number }): Promise<AxiosResponse<{ data: KnowledgeBase[], total: number }>>`: Fetches a list of KBs.
        *   `GET /knowledge-bases`
    *   `getById(id: number): Promise<AxiosResponse<KnowledgeBase>>`: Fetches a single KB.
        *   `GET /knowledge-bases/${id}`
    *   `create(data: KnowledgeBaseCreate): Promise<AxiosResponse<KnowledgeBase>>`: Creates a new KB.
        *   `POST /knowledge-bases`
    *   `update(id: number, data: KnowledgeBaseUpdate): Promise<AxiosResponse<KnowledgeBase>>`: Updates a KB.
        *   `PUT /knowledge-bases/${id}`
    *   `delete(id: number): Promise<AxiosResponse<void>>`: Deletes a KB.
        *   `DELETE /knowledge-bases/${id}`
    *   `uploadDocument(kbId: number, file: File, onUploadProgress?: (progressEvent: any) => void): Promise<AxiosResponse<DocumentResponse>>`: Uploads a document to a KB.
        *   `POST /knowledge-bases/${kbId}/upload-document` (uses `FormData` for file upload)
    *   `getKbDocuments(kbId: number, params: { limit?: number, offset?: number }): Promise<AxiosResponse<{ data: DocumentResponse[], total: number }>>`: Fetches documents for a specific KB.
        *   `GET /knowledge-bases/${kbId}/documents`

#### 3.5.4. Document Service (`document.ts`)
File: `frontend/src/api/document.ts`

*   **Purpose:** Handles CRUD operations for individual documents (if not fully covered by `knowledgeBase.ts`).
*   **Uses:** `apiClient`.
*   **Key Interfaces/Types:**
    *   `DocumentResponse`, `DocumentUpdate`: For document structure and payloads.
*   **Key Methods (examples):**
    *   `getById(id: number): Promise<AxiosResponse<DocumentResponse>>`: Fetches a single document.
        *   `GET /document/${id}`
    *   `update(id: number, data: DocumentUpdate): Promise<AxiosResponse<DocumentResponse>>`: Updates document metadata.
        *   `PUT /document/${id}`
    *   `delete(id: number): Promise<AxiosResponse<void>>`: Deletes a document.
        *   `DELETE /document/${id}`

### 3.6. Frontend State Management (Pinia)
Located in `frontend/src/stores/`. Pinia is used for centralized state management.

#### 3.6.1. Pinia Setup (`stores/index.ts`)
File: `frontend/src/stores/index.ts`

*   **Purpose:** Initializes and exports the main Pinia instance.
*   **Example Structure:**
    ```typescript
    import { createPinia } from 'pinia'
    // Optionally, import PiniaPersist plugin if used
    // import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'

    const pinia = createPinia()
    // if (piniaPluginPersistedstate) {
    //   pinia.use(piniaPluginPersistedstate)
    // }

    export default pinia
    ```
*   This `pinia` instance is then used in `main.ts` (`app.use(pinia)`).

#### 3.6.2. Auth Store (`stores/auth.store.ts`)
File: `frontend/src/stores/auth.store.ts`

*   **Purpose:** Manages authentication state (user, token, login status).
*   **Structure (`defineStore`):**
    *   `id`: Unique identifier (e.g., `'auth'`).
    *   `state`: A function returning the initial state object.
        *   `token: string | null` (persisted in localStorage)
        *   `user: User | null` (User type defined elsewhere, e.g., `{ id: number, username: string, email: string }`)
        *   `isAuthenticated: boolean` (could be a getter)
        *   `returnUrl: string | null`
    *   `getters`: Computed properties derived from state.
        *   `isAuthenticated: (state) => !!state.token && !!state.user`
        *   `currentUser: (state) => state.user`
    *   `actions`: Methods to modify state or perform asynchronous operations.
        *   `login(credentials: LoginCredentials): Promise<void>`: Calls auth API, on success stores token and user, sets `isAuthenticated`.
        *   `logout(): void`: Clears token and user, sets `isAuthenticated` to false, redirects to login.
        *   `register(details: RegisterDetails): Promise<void>`: Calls registration API.
        *   `fetchUser(): Promise<void>`: Fetches user details using the stored token.
        *   `setToken(token: string | null)`: Sets token and updates localStorage.
        *   `setUser(user: User | null)`: Sets user data.
*   **Persistence:**
    *   Often uses `pinia-plugin-persistedstate` to keep parts of the store (like the token) synchronized with localStorage.
    *   Configuration for persistence is done within the `defineStore` options:
        ```typescript
        export const useAuthStore = defineStore('auth', {
          state: () => ({
            token: null as string | null,
            user: null as User | null,
            // ...
          }),
          // ... getters and actions
          persist: { // If using pinia-plugin-persistedstate
            paths: ['token', 'user'], // Specify which parts of state to persist
          },
        })
        ```

---

## 4. Workflow Engine (`med-rag-flow/`)

### 4.1. Workflow Overview
The `med-rag-flow/` directory contains a data processing pipeline built with Python and Prefect. Its primary purpose is to handle the batch processing of PDF documents for integration into the RAG system.

**Key Functions:**
1.  **Document Ingestion:** Monitors a designated input directory (e.g., `med-rag-flow/input_pdfs/`) for new PDF files.
2.  **Parsing:** Extracts text content from PDF documents.
3.  **Chunking:** Splits the extracted text into smaller, manageable chunks suitable for vector embedding.
4.  **Vector Generation:** Converts text chunks into numerical vector embeddings using a specified embedding model (e.g., Sentence Transformers).
5.  **Storage:** Stores the generated vectors in a vector database (e.g., FAISS, ChromaDB, Milvus) and saves the index to a path associated with a Knowledge Base ID.
6.  **Backend Integration:** Communicates with the FastAPI backend to:
    *   Create or update document records in the main database.
    *   Update the status of knowledge bases and documents (e.g., "processing", "completed").
    *   Store the path to the generated vector index for the relevant knowledge base.

**Workflow Trigger:**
*   Can be manually triggered.
*   Can be scheduled to run periodically (e.g., daily).
*   Could potentially be triggered via an API call from the backend when new documents are uploaded to a "staging" area for a knowledge base.

### 4.2. Workflow Setup
**Prerequisites:**
*   Python 3.9+
*   Poetry (for managing Python dependencies in this sub-project as well, if isolated) or a `requirements.txt`.

**Steps:**
1.  **Navigate to the workflow directory:**
    ```bash
    cd med-rag-flow/
    ```
2.  **Install dependencies:**
    *   If using Poetry: `poetry install`
    *   If using `requirements.txt`: `pip install -r requirements.txt`
    *   Key dependencies include: `prefect`, `langchain` (or similar for chunking/embeddings), PDF parsing libraries (`pypdf2`, `pdfminer.six`), vector database clients, HTTP clients (`requests`, `httpx`).
3.  **Configuration (`config.py` or `.env`):**
    *   `INPUT_PDF_DIR`: Path to the directory where new PDFs are placed.
    *   `PROCESSED_DIR`: Path to move PDFs after successful processing.
    *   `FAILED_DIR`: Path to move PDFs if processing fails.
    *   `VECTOR_STORE_BASE_PATH`: Base path to save generated vector indexes.
    *   `EMBEDDING_MODEL_NAME`: Name or path of the sentence transformer model.
    *   `CHUNK_SIZE`, `CHUNK_OVERLAP`: Parameters for text chunking.
    *   `BACKEND_API_URL`: URL of the FastAPI backend for updates.
    *   `LOG_LEVEL`.
4.  **Prefect Setup (Local):**
    *   Ensure Prefect is installed.
    *   You might need to configure a Prefect backend (e.g., local SQLite server, Prefect Cloud). For simple local execution, defaults might suffice.
    *   `prefect server start` (if running a local Prefect Orion/UI server for monitoring).

### 4.3. Running Workflows
Workflows are defined as Python scripts using Prefect's `@flow` and `@task` decorators.

1.  **Define Flows:**
    *   A main flow (e.g., `process_documents_flow` in a file like `med-rag-flow/main_flow.py`) orchestrates the tasks.
    *   Tasks might include: `scan_for_new_pdfs`, `parse_pdf`, `chunk_text`, `generate_embeddings`, `save_to_vector_store`, `update_backend_status`.
2.  **Register and Run Flows (Prefect 2.x):**
    *   **Directly run the Python script containing the flow:**
        ```bash
        python med-rag-flow/main_flow.py 
        ```
        (Assuming the script calls the flow function directly at the end for execution).
    *   **Using Prefect CLI for deployments (more advanced):**
        *   Create a deployment for the flow:
            ```bash
            prefect deployment build ./main_flow.py:process_documents_flow -n pdf-processing-deployment -q default
            ```
        *   Apply the deployment:
            ```bash
            prefect deployment apply process_documents_flow-deployment.yaml
            ```
        *   Start an agent to pick up work from the 'default' work queue:
            ```bash
            prefect agent start -q default
            ```
        *   Then, you can trigger flow runs from the Prefect UI or CLI:
            ```bash
            prefect deployment run process_documents_flow/pdf-processing-deployment
            ```
3.  **Monitoring:**
    *   If using a Prefect server (local or cloud), flow runs and their statuses can be monitored via the Prefect UI.
    *   Logs are typically output to the console and/or stored by Prefect.

The specific command to run the workflow will depend on how the Prefect flows are structured and deployed within the `med-rag-flow` directory.

---
