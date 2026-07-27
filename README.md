# AI Chat Backend — RAG-Powered Chatbot API
by revan8mata

A production-style backend for building AI-powered chat applications, with document-grounded answers (RAG), streaming responses, multi-provider LLM support, and event-driven webhooks.

Built as a learning project and freelance portfolio piece — designed to be genuinely deployable, not just a tutorial exercise.

## Features

- **Retrieval-Augmented Generation (RAG)** — upload PDF/text documents, get chunked, embedded, and stored as vectors. Chat responses are grounded in your own documents instead of relying purely on the LLM's training data.
- **Streaming responses** — token-by-token delivery via Server-Sent Events, same UX as ChatGPT/Claude, instead of waiting for a full response.
- **Multi-provider LLM support** — switch between Gemini and OpenAI per-request, with a clean provider abstraction layer for adding more providers later.
- **Two deployable business models** (separate branches):
  - `main` — shared knowledge base, admin-managed documents, all users query the same source (built for SaaS support bots / unified knowledge base use cases)
  - `personal-rag` — per-user private documents, each user only queries their own uploads (built for apps needing per-user data isolation)
- **JWT authentication** with role-based access control (admin vs regular user)
- **Rate limiting** — both request-count-based and token-count-based (Redis), protecting against abuse and controlling LLM API costs
- **Webhooks** — event-driven notifications (`document_uploaded`, `new_conversation`, `delete_conversation`) with automatic retry (exponential backoff) and concurrent delivery to multiple registered endpoints
- **Input validation** — enforced password/username rules via Pydantic validators

## Tech Stack

- **API:** FastAPI (Python, async)
- **Database:** PostgreSQL + pgvector (vector similarity search)
- **Cache/Rate limiting:** Redis
- **LLM providers:** Google Gemini, OpenAI
- **Migrations:** Alembic
- **Containerization:** Docker + docker-compose

## Architecture Overview

```
Client
  │
  ├── POST /docs           → upload document → chunk → embed → store vectors
  ├── POST /talk            → start conversation → retrieve relevant chunks → stream LLM response
  ├── POST /conversations/{id}/messages → continue conversation (same flow, with history)
  ├── POST /webhook         → register a webhook (url + event type)
  └── GET  /stats           → admin-only usage analytics
```

Every chat request:
1. Embeds the user's message
2. Runs a cosine-similarity search against stored document chunks (pgvector)
3. Injects the most relevant chunks into the LLM prompt as context
4. Streams the response back token-by-token
5. Fires relevant webhooks (non-blocking, via FastAPI BackgroundTasks) once the DB transaction is confirmed successful

## Setup

```bash
# clone and enter the repo
git clone <your-repo-url>
cd ai-chat-backend

# copy and fill in environment variables
cp .env.example .env

# start everything (API + Postgres/pgvector + Redis)
docker-compose up -d --build

# run migrations
docker-compose exec api python -m alembic upgrade head
```

API docs available at `http://localhost:8000/docs` once running.

## Environment Variables

```
DATABASE_HOSTNAME=db
DATABASE_PORT=5432
DATABASE_USERNAME=postgres
DATABASE_PASSWORD=your_password
DATABASE_NAME=ai_chat
SECRET_KEY=your_jwt_secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=120
API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key
```

## Branches

- `main` — business/shared-knowledge-base RAG model
- `personal-rag` — per-user private document RAG model

## Status

Actively developed learning project. Built solo over ~1 week, covering RAG pipelines, streaming architecture, concurrency (asyncio), Redis-based rate limiting, and webhook delivery systems with retry logic.

## Contact

Open to freelance work — AI integrations, RAG systems, FastAPI backends.
