# Monorepo Chatbota RAG

Lokalny system RAG do zarządzania dokumentami i udostępniania osadzanego widżetu czatu.

## Stack

Projekt składa się z:

- `apps/admin` - panel administracyjny React/Vite do przesyłania dokumentów, podglądu cytowań i reindeksacji
- `apps/widget` - osadzalny widżet React udostępniający `window.RagWidget.init(...)`
- `apps/site` - statyczna strona demonstracyjna osadzająca widżet pod `http://localhost:3000`
- `services/api` - API FastAPI, worker RQ, migracje Alembic i pipeline przetwarzania dokumentów
- `postgres` - baza PostgreSQL z `pgvector`
- `redis` - kolejka zadań
- `ollama` - instancja czatu, aktualnie uruchamiana z GPU
- `ollama-embed` - osobna instancja Ollama dla embeddingów

## Architektura uruchomieniowa

Usługi zdefiniowane w [docker-compose.yml](/H:/projekty/raglocalchatbot/docker-compose.yml):

- `postgres` na porcie `5432`
- `redis` na porcie `6379`
- `ollama` na porcie `11434`
- `api` na porcie `8000`
- `admin` na porcie `4173`
- `widget` na porcie `8080`
- `site` na porcie `3000`

Istotne zachowania:

- `api` przy starcie automatycznie uruchamia `alembic upgrade head`
- aplikacja przy starcie tworzy konto administratora tylko wtedy, gdy jeszcze nie istnieje
- hasło administratora nie jest resetowane przy każdym restarcie
- modele czatu i embeddingów działają na osobnych instancjach Ollama
- `ollama` jest skonfigurowana do użycia GPU przez `gpus: all`

## Wymagania

### Wariant zalecany

- Windows z Docker Desktop
- Docker Desktop działający na WSL2
- karta NVIDIA dostępna w Dockerze
- wolne porty: `3000`, `4173`, `5432`, `6379`, `8000`, `8080`, `11434`

### Wariant CPU-only

Repo jest obecnie skonfigurowane pod GPU. Na maszynie bez GPU trzeba ręcznie dostosować konfigurację.

Minimalny zestaw zmian:

1. W `.env` ustaw lżejszy model czatu, na przykład:

```env
OLLAMA_CHAT_MODEL=gemma3:4b
```

2. W [docker-compose.yml](/H:/projekty/raglocalchatbot/docker-compose.yml) usuń linię `gpus: all` z usługi `ollama`, tak aby wyglądała tak:

```yaml
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama:/root/.ollama
```

3. Przebuduj i uruchom stack:

```powershell
docker compose up -d --build
```

4. Pobierz modele dla wariantu CPU:

```powershell
docker compose exec ollama ollama pull gemma3:4b
docker compose exec ollama-embed ollama pull nomic-embed-text
```

Uwagi operacyjne:

- `qwen3.5:9b` na CPU będzie wyraźnie wolniejszy od `gemma3:4b`
- `ollama-embed` może pozostać bez zmian
- jeśli komputer ma mało RAM, warto zostać przy mniejszym modelu czatu

## Konfiguracja

Projekt korzysta z pliku [.env](/H:/projekty/raglocalchatbot/.env). W repo jest też gotowy wzorzec [.env.example](/H:/projekty/raglocalchatbot/.env.example).

Najważniejsze ustawienia bieżącego stacku:

- `OLLAMA_CHAT_MODEL=qwen3.5:9b`
- `OLLAMA_EMBEDDING_MODEL=nomic-embed-text`
- `OLLAMA_BASE_URL=http://ollama:11434`
- `OLLAMA_EMBEDDING_BASE_URL=http://ollama-embed:11434`
- `OLLAMA_CHAT_KEEP_ALIVE=-1`
- `OLLAMA_EMBEDDING_KEEP_ALIVE=30m`
- `OLLAMA_PRELOAD_MODELS_ON_STARTUP=true`
- `ADMIN_EMAIL=admin@example.com`
- `ADMIN_PASSWORD=change-me`

Jeśli uruchamiasz projekt na nowym komputerze, skopiuj `.env.example` do `.env`, a potem w razie potrzeby dostosuj wartości.

## Instalacja na nowym komputerze

1. Zainstaluj Docker Desktop.
2. Upewnij się, że Docker działa poprawnie.
3. Sklonuj repozytorium.
4. Skopiuj `.env.example` do `.env`.
5. Uruchom cały stack:

```powershell
docker compose up -d --build
```

6. Pobierz modele Ollama:

```powershell
docker compose exec ollama ollama pull qwen3.5:9b
docker compose exec ollama-embed ollama pull nomic-embed-text
```

7. Sprawdź, czy usługi działają:

```powershell
Invoke-WebRequest http://localhost:8000/api/health
Invoke-WebRequest http://localhost:4173
Invoke-WebRequest http://localhost:3000
Invoke-WebRequest http://localhost:8080/widget.js
```

## Logowanie administratora

Przy pierwszym starcie aplikacja utworzy administratora na podstawie `.env`:

- e-mail: `admin@example.com`
- hasło: `change-me`

Implementacja bootstrapu jest w:

- [main.py](/H:/projekty/raglocalchatbot/services/api/app/main.py)
- [admin.py](/H:/projekty/raglocalchatbot/services/api/app/services/admin.py)

Jeżeli konto już istnieje, ponowny start aplikacji go nie nadpisze.

## Modele Ollama

Aktualny układ modeli:

- czat: `qwen3.5:9b`
- embeddingi: `nomic-embed-text`

Działanie:

- `ollama` obsługuje model czatu
- `ollama-embed` obsługuje embeddingi
- dzięki rozdzieleniu embeddingi nie wypychają modelu czatu z pamięci

## Endpointy użytkowe

Panel administratora:

- `POST /api/admin/login`
- `POST /api/admin/logout`
- `GET /api/admin/me`
- `GET /api/admin/documents`
- `POST /api/admin/documents`
- `POST /api/admin/documents/{id}/reindex`
- `DELETE /api/admin/documents/{id}`
- `GET /api/admin/documents/{id}/citations`
- `GET /api/admin/jobs/{id}`

Widżet publiczny:

- `POST /api/chat/sessions`
- `POST /api/chat/messages`

## Kluczowe funkcje

- logowanie administratora przez cookie sesyjne
- przesyłanie plików `.pdf`, `.docx`, `.doc`, `.txt`
- odrzucanie PDF-ów skanowanych lub obrazkowych bez OCR
- hybrydowe wyszukiwanie: `pgvector` + full text search w PostgreSQL
- odpowiedzi oparte wyłącznie na źródłach
- cytowania w odpowiedziach i w panelu administratora
- osobny worker do ingestii i reindeksacji
- pomiary czasu odpowiedzi w `Server-Timing` i logach API

## Adresy lokalne

Po uruchomieniu:

- panel administratora: [http://localhost:4173](http://localhost:4173)
- strona demo: [http://localhost:3000](http://localhost:3000)
- API: [http://localhost:8000](http://localhost:8000)
- pakiet widżetu: [http://localhost:8080/widget.js](http://localhost:8080/widget.js)
- Ollama: [http://localhost:11434](http://localhost:11434)

## Użycie widżetu

```html
<script src="http://localhost:8080/widget.js"></script>
<script>
  window.RagWidget.init({
    apiBaseUrl: "http://localhost:8000",
    siteKey: "local-demo-key",
    title: "Zapytaj bazę wiedzy"
  });
</script>
```

## Debug i diagnostyka

Przydatne komendy:

```powershell
docker compose logs api --tail 50
docker compose logs worker --tail 50
docker compose exec ollama ollama ps
docker compose exec ollama ollama list
docker compose exec ollama-embed ollama ps
```

Jeśli odpowiedzi są wolne, sprawdzaj przede wszystkim:

- `Server-Timing` w `POST /api/chat/messages`
- logi `chat_timing` w API
- użycie CPU/GPU przez `ollama`

## Ograniczenia

- obecny domyślny model czatu jest sensowny głównie dla maszyn z GPU NVIDIA
- bez GPU odpowiedzi będą wyraźnie wolniejsze albo trzeba użyć mniejszego modelu
- OCR dla skanowanych PDF-ów nie jest zaimplementowany w wersji bieżącej