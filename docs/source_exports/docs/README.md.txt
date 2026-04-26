FILE: README.md
COMPONENT: docs
================================================================================
# AI-Powered Customer Support Chatbot (OpenNLP + Lucene)

Conversational customer-support chatbot with:
- **Apache OpenNLP** (intent classification + entity extraction)
- **Apache Lucene** (FAQ/knowledge-base search)
- **Kafka** (real-time chat audit stream)
- **FastAPI** (API gateway + orchestration + context/state)
- **React** (chat UI + analytics dashboard)
- **Docker Compose** (one-command local stack)

## Architecture (high level)
- `chat-ui` (React) → calls → `backend` (FastAPI)
- `backend` → calls → `lucene` (Java Spark service: OpenNLP + Lucene)
- `backend` → publishes audit events → `kafka` topic `chat_logs`
- `consumer` → reads `chat_logs` → writes → `chat-logs` volume as `chat_logs.jsonl`
- `backend` → aggregates analytics from `chat_logs.jsonl` via `/analytics`
- `redis` stores per-user session/state (with in-memory fallback if Redis is unavailable)

## Quick start (Docker)
1. Start everything:
   - `docker compose up --build`
2. Open:
   - UI: `http://localhost:3000`
   - FastAPI: `http://localhost:8000/docs`
   - Java NLP/Search health: `http://localhost:4567/health`

## Services and ports
- `frontend` (React): `3000`
- `backend` (FastAPI): `8000`
- `lucene` (Java Spark): `4567`
- `kafka`: `9092`
- `redis`: `6379`

## Knowledge base (Lucene)
The Java service indexes built-in FAQ entries + optional file-based entries from:
- `backend/data/faq.txt` (mounted as `/app/data/faq.txt` in the `lucene` container)

Format (one per line):
`question | answer | intent`

`intent` is optional (defaults to `kb_faq`).

## OpenNLP models
The `lucene` service loads OpenNLP models from:
- `backend/data/models` (mounted as `/app/data/models`)

At startup it auto-trains **intent** model `en-intent.bin` if missing using:
- `backend/data/intents.json`

Tokenizer/person NER models are expected at:
- `/app/data/models/en-token.bin`
- `/app/data/models/en-ner-person.bin`

If they are missing, the service still runs (with degraded tokenization / name detection).

## FastAPI endpoints
- `POST /chat` main chatbot endpoint
- `GET /health` liveness + session-store status
- `GET /analytics` aggregated metrics for the dashboard

## Multi-language translation
Translation is enabled by default. The gateway:
- detects the user’s input language,
- translates user input to English for NLP,
- translates the bot response back to the user’s language.

To disable translation (offline mode):
- set `ENABLE_TRANSLATION=0` on the `backend` service.

## “Serverless function” demo
`backend/functions/recommendation.py` contains a `lambda_handler(...)` used by the chatbot
for `product_recommendation` intent (stateless recommendation logic).

## Demo video outline (suggested)
1. Start stack with Docker Compose
2. Show chat: greeting, FAQ answer (Lucene hit), order tracking (state machine), recommendation
3. Show escalation triggered by negative sentiment
4. Show analytics dashboard updating as chats occur

## Report template
See `docs/REPORT.md`.

