# RAG Chatbot Monorepo

Greenfield RAG system with:

- `apps/admin`: React/Vite admin SPA for document management
- `apps/widget`: embeddable React widget exposing `window.RagWidget.init(...)`
- `apps/site`: static demo website embedding the widget on `http://localhost:3000`
- `services/api`: FastAPI API, RQ worker, Alembic migrations, and ingestion pipeline

## Development

1. Copy `.env.example` to `.env`.
2. Install frontend dependencies with `npm.cmd install`.
3. Install Python dependencies inside a Python 3.11 environment using `pip install -e services/api[dev]`.
4. Run the API migrations with `alembic upgrade head` from `services/api`.
5. Start the full stack with `docker compose up --build`.
6. Pull the default local models after Ollama is up:
   - `docker compose exec ollama ollama pull llama3.2:1b`
   - `docker compose exec ollama ollama pull nomic-embed-text`

## Runtime services

- PostgreSQL + `pgvector`
- Redis
- Ollama
- FastAPI API
- RQ worker
- Nginx-served admin SPA on port `4173`
- Widget bundle on port `8080` with `widget.js`
- Demo site on port `3000`

## Key behaviors

- Admin login via session cookie
- Upload, reindex, delete, and citation preview for `.pdf`, `.docx`, `.doc`, and `.txt`
- Hybrid retrieval using `pgvector` similarity plus PostgreSQL text search
- Public chat widget with anonymous sessions, origin validation, and rate limiting
- Grounded responses only, with citations

## Public endpoints

- `POST /api/admin/login`
- `POST /api/admin/logout`
- `GET /api/admin/me`
- `GET /api/admin/documents`
- `POST /api/admin/documents`
- `POST /api/admin/documents/{id}/reindex`
- `DELETE /api/admin/documents/{id}`
- `GET /api/admin/documents/{id}/citations`
- `GET /api/admin/jobs/{id}`
- `POST /api/chat/sessions`
- `POST /api/chat/messages`

## Widget usage

```html
<script src="http://localhost:8080/widget.js"></script>
<script>
  window.RagWidget.init({
    apiBaseUrl: "http://localhost:8000",
    siteKey: "local-demo-key"
  });
</script>
```

## Demo site

Open `http://localhost:3000` to try the widget on a sample page that is already configured against the local API and widget bundle.
