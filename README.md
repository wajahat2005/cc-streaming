# AI-Powered Customer Support Chatbot (FastAPI + OpenNLP + Lucene + Kafka + React)

Final Year Project (Cloud Computing / NLP): a production-style customer support chatbot that combines:
- **Natural Language Understanding** (intent + entities)
- **Knowledge Base Search** (Lucene fuzzy retrieval for FAQs)
- **Conversation Memory** (Redis session state)
- **Real-time Logging & Analytics** (Kafka → consumer → metrics)
- **Modern UI** (React + Vite build served via Nginx)

---

## Project Overview
This chatbot answers common support questions, supports multi-turn order tracking, and provides basic product recommendations. It uses a hybrid approach:
- Deterministic rules for critical flows (order tracking, escalation safety)
- Model-based intent classification + entity extraction (OpenNLP + local fallback)
- Lucene search when confidence/scores are strong enough (to avoid “wrong answers”)

---

## Architecture (Simple Explanation)
**FastAPI (Backend / Brain)**  
Receives messages from the frontend, manages session state in Redis, calls the Java NLP/Lucene service, applies decision logic, and returns a structured response.

**Java Microservice (Apache OpenNLP + Apache Lucene)**  
Exposes a REST API that runs intent classification + entity extraction and performs Lucene fuzzy search over the FAQ knowledge base.

**Kafka (Logging Pipeline)**  
Backend publishes each interaction (user message, response, intent, sentiment, language). A consumer stores logs to disk for analytics.

**React (Frontend / UI)**  
Chat interface that calls the backend API and displays response + metadata.

---

## Features
- **Intent Recognition** with confidence thresholds (avoids irrelevant answers)
- **Entity Extraction** (order IDs, names, locations/products where available)
- **Order Tracking Flow**
  - “Where is my order?” → asks for order ID
  - “12345 / ORD-12345 / #12345” → returns tracking status
- **Product Recommendations** (deterministic logic + backend function)
- **Sentiment Handling** with safe escalation rule (`sentiment < -0.6`)
- **Multi-language Support** (message translation in/out when enabled)
- **Analytics**
  - `/analytics` endpoint for summary stats
  - Kafka audit stream (topic: `chat_logs`)

---

## Repository Structure (University Requirement)
```
cc-project-group10/
├── docker-compose.yml
├── .env.example
├── src/
│   ├── backend/      # FastAPI + Kafka producer/consumer + tests
│   ├── frontend/     # React UI (Vite build served by Nginx)
│   └── ai-chatbot/   # Java microservice (OpenNLP + Lucene)
├── config/
├── docs/
├── scripts/
├── results/
└── .github/workflows/
```

---

## Quick Start (Docker Compose)
### Prerequisites
- Docker Desktop (with Compose)

### Run
```bash
git clone <YOUR_REPO_URL>
cd cc-project-group10
docker compose up --build
```

### URLs
- Frontend: http://localhost:3000
- Backend OpenAPI docs: http://localhost:8000/docs
- Backend health: http://localhost:8000/health
- Java NLP/Lucene health: http://localhost:4567/health

---

## Docker Services (Ports)
- `frontend` → `3000:3000`
- `backend` → `8000:8000`
- `lucene` (Java NLP/Lucene) → `4567:4567`
- `kafka` → `9092:9092`
- `zookeeper` → `2181:2181`
- `redis` → `6379:6379`

---

## API Endpoints
### Backend (FastAPI)
- `POST /chat`  
  Request:
  ```json
  { "message": "where is my order", "user_id": "u1", "lang": "en" }
  ```
  Response includes:
  - `response` (final message)
  - `intent`, `confidence` (0–100), `sentiment`
  - `entities` (extracted data)
  - `session_context` (memory state)

- `GET /health`  
  Shows API status + Redis mode + Java service connectivity.

- `GET /analytics`  
  Returns aggregated analytics (safe to call; should never crash).

- `GET /metrics`  
  Simplified metrics payload for monitoring/report marks.

### Java NLP/Lucene Service
- `POST /search`  
  Request:
  ```json
  { "query": "refund policy", "topK": 3 }
  ```
  Response includes `intent`, `confidence`, `entities`, and Lucene `hits`.

- `GET /health`

---

## Testing
From repo root:
```bash
docker compose up -d --build
docker compose exec backend pytest -q
```

---

## Artifacts & Deliverables
- **Final Technical Report (PDF)**: [View Report](./docs/report.pdf) (See also [Markdown version](./docs/REPORT.md))
- **Presentation Slides**: [View Presentation](./docs/presentation.pdf)
- **Demo Video**: [YouTube Link](https://youtube.com/unlisted-link-here)
- **Project Board**: [GitHub Issues Board](https://github.com/cc-streaming-group10/issues)
- **Release Version**: v1.0

---

## Screenshots (Placeholder)
Add screenshots here for your report/demo:
- `docs/screenshots/chat-ui.png`
- `docs/screenshots/analytics.png`
- `docs/screenshots/docker-compose-healthy.png`

---

## Contributors
- **Group 10**
  - M wajahat
  - Shayan Afzal
---

## License
See `LICENSE`.
