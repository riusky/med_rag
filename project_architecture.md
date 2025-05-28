# Project Architecture Document

This document outlines the architecture of the project, including static structure, dynamic data flows, and key dependencies.

## 1. Static Architecture Diagram

This diagram provides a high-level overview of the main components of the system and their relationships.

```plantuml
@startuml
!theme materia

package "Frontend (Vue.js)" {
  [UI Components]
  [API Client] -down-> [Server API]
  [Router]
  [State Management]
}

package "Server (Python/FastAPI)" {
  [Server API] -down-> [Services]
  [Services] -down-> [Database (PostgreSQL)]
  [Services] -down-> [Task Queue (Redis/Celery)]
  [Database (PostgreSQL)]
  [Task Queue (Redis/Celery)] -down-> [med-RAG Flow]
}

package "med-RAG Flow (Python)" {
  [Flow Orchestrator] -down-> [LLM Service]
  [Flow Orchestrator] -down-> [Vector Store]
  [Document Processing Tasks]
  [Embedding Tasks]
  [LLM Tasks]
  [LLM Service]
  [Vector Store]
}

[User] -up-> [Frontend (Vue.js)]
@enduml
```

## 2. Dynamic Data Flow Diagram

This diagram illustrates how data flows through the system during key operations, specifically for Q&A and Document Ingestion processes.

```plantuml
@startuml
!theme materia

title Data Flow Diagram

actor User
participant Frontend
participant Server
participant "med-RAG Flow" as MedRAGFlow
database Database
database "Vector Store" as VectorStore
participant "LLM Service" as LLMService

== Q&A Flow ==

User -> Frontend: Submits question
Frontend -> Server: Sends question via API
Server -> MedRAGFlow: Initiates Q&A task with question
MedRAGFlow -> VectorStore: Searches for relevant document chunks
VectorStore --> MedRAGFlow: Returns relevant chunks
MedRAGFlow -> LLMService: Sends question and chunks for answer generation
LLMService --> MedRAGFlow: Returns generated answer
MedRAGFlow --> Server: Returns answer
Server --> Frontend: Sends answer
Frontend -> User: Displays answer

== Document Ingestion Flow ==

User -> Frontend: Uploads document
Frontend -> Server: Sends document via API
Server -> Database: Stores document metadata
Database --> Server: Confirms metadata storage
Server -> MedRAGFlow: Initiates document processing task with document
MedRAGFlow -> MedRAGFlow: Performs document processing (e.g., chunking)
MedRAGFlow -> LLMService: (Optional) Sends chunks for further processing (e.g., summarization, metadata extraction)
LLMService --> MedRAGFlow: (Optional) Returns processed chunks
MedRAGFlow -> VectorStore: Embeds and stores document chunks
VectorStore --> MedRAGFlow: Confirms chunk storage
MedRAGFlow --> Server: Confirms document processing completion
Server -> Frontend: Notifies user of completion
User <- Frontend: Sees document processing status

@enduml
```

## 3. Overall Dependency Diagram

This diagram shows the key external libraries, frameworks, and services that each major component of the project depends on.

```plantuml
@startuml
!theme materia

title Project Dependency Diagram

package "Frontend" {
  [Vue.js]
  [Vue Router]
  [Pinia]
  [Axios]
  [Tailwind CSS]
  [Vite]
  [UI Libraries]
}

package "Server" {
  [FastAPI]
  [SQLAlchemy]
  [Asyncpg (PostgreSQL Driver)]
  [Pydantic]
  [Taskiq (Task Queue)]
  [Gunicorn/Uvicorn]
  [Logging (Loguru)]
}

package "med-RAG Flow" {
  [Langchain]
  [Document Loaders]
  [Text Splitters]
  [Embedding Models]
  [LLM Wrappers]
}

database "PostgreSQL" as DB
cloud "LLM Service (e.g., Ollama)" as LLM
database "Vector Store (e.g., FAISS)" as VectorDB
hexagon "Task Queue Broker (e.g., Redis)" as Broker

Frontend -down-> Server : "API Calls (HTTP/S)"

Server -down-> DB : "CRUD Operations (SQL)"
Server -down-> Broker : "Task Enqueue/Dequeue"
Server -down-> "med-RAG Flow" : "Invoke RAG Logic"

"med-RAG Flow" -down-> LLM : "Prompts & Queries"
"med-RAG Flow" -down-> VectorDB : "Store & Retrieve Embeddings"
"med-RAG Flow" -up-> Server : "Return Results"


note right of Frontend
  Key Dependencies:
  - Vue.js & Ecosystem
  - Axios (HTTP Client)
  - Tailwind CSS
  - Vite (Build Tool)
end note

note left of Server
  Key Dependencies:
  - FastAPI (Web Framework)
  - SQLAlchemy (ORM)
  - Taskiq (Async Tasks)
  - Pydantic (Validation)
  - Langchain, Ollama, FAISS (via med-RAG Flow integration)
end note

note right of "med-RAG Flow"
  Key Dependencies:
  - Langchain (Core RAG Framework)
  - LLM Interaction Libraries
  - Vector Store Client Libraries
  - Document Processing Libraries
end note
@enduml
```
