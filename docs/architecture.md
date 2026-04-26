# System Architecture

This document outlines the high-level architecture of the Pro-Grade AI Assistant. The system is built using a microservices pattern, orchestrating various components to deliver a scalable, multilingual, and highly available customer support chatbot.

## System Diagram

```mermaid
flowchart TD
    subgraph Client Layer
        React[React Frontend (UI)]
    end

    subgraph API Gateway & Orchestration
        FastAPI[FastAPI Backend (Python)]
        Redis[(Redis Session Store)]
    end

    subgraph AI Engine Layer
        Lucene[Lucene / OpenNLP Microservice (Java)]
        HuggingFace[HuggingFace local fallback]
    end

    subgraph Data Pipeline & Monitoring
        Kafka[Kafka Broker]
        Zookeeper[Zookeeper]
        Consumer[Python Audit Consumer]
        Logs[(Log Volume)]
        Prometheus[Prometheus Metrics]
        Grafana[Grafana Dashboards]
    end

    React -- "REST (JSON) :3000" --> FastAPI
    FastAPI -- "State & Context :6379" --> Redis
    FastAPI -- "REST / Search :4567" --> Lucene
    FastAPI -- "Metrics Scrape :9090" --> Prometheus
    Prometheus -- "Visualize :3001" --> Grafana
    
    FastAPI -- "Produce Logs :9092" --> Kafka
    Kafka -- "Manage State :2181" --> Zookeeper
    Consumer -- "Consume Logs" --> Kafka
    Consumer -- "Write to Disk" --> Logs
```

## Component Interaction

1.  **Frontend (React)**: The user interface layer running on port `3000`. It captures user input and sends it to the backend via REST API. It receives JSON responses detailing the bot's reply, detected intent, and metadata, rendering them in a chat window.
2.  **Backend (FastAPI)**: The central orchestrator running on port `8000`. It performs initial preprocessing, handles translation, maintains session state, and queries the AI Engine for intent detection and fuzzy matching.
3.  **Redis**: Acts as a high-speed, in-memory session store (port `6379`). It keeps track of user context, ongoing flows (e.g., waiting for an order ID), and message history to provide a seamless conversational experience.
4.  **Lucene (AI Engine)**: A Java-based microservice (port `4567`) utilizing Apache OpenNLP and Lucene. It receives preprocessed text from the backend, performs Named Entity Recognition (NER), intent classification, and fuzzy searches against the knowledge base (FAQ).
5.  **Kafka & Zookeeper**: Kafka (port `9092`) acts as the event broker for asynchronous chat logging and auditing. Zookeeper (port `2181`) manages the Kafka cluster state.
6.  **Audit Consumer**: A Python background worker that subscribes to the Kafka `chat_logs` topic and persists conversation data to disk for analytics.
7.  **Monitoring Stack (Prometheus & Grafana)**: Prometheus (port `9090`) scrapes the FastAPI `/metrics` endpoint. Grafana (port `3001`) visualizes these time-series metrics on pre-configured dashboards.

## Data Flow: Frontend → Backend → Kafka → Consumer

The critical path for processing a user message and logging the interaction is as follows:

1.  **Ingestion**: The Frontend sends a `POST /chat` request to the Backend containing the user's raw message, user ID, and preferred language.
2.  **Processing**:
    *   The Backend translates the message to English (if necessary).
    *   It retrieves the user's current session state from Redis.
    *   It forwards the query to the Lucene AI Engine for NLP and intent analysis.
    *   Based on the returned intent, confidence score, and internal deterministic rules, the Backend formulates a response.
    *   The response is translated back to the user's original language.
3.  **Response Delivery**: The Backend sends the formatted response back to the Frontend.
4.  **Asynchronous Logging**: 
    *   Simultaneously, the Backend produces a log event containing the raw message, bot response, detected intent, sentiment, and session data.
    *   This event is published to the Kafka broker on the `chat_logs` topic.
5.  **Persistence**:
    *   The Audit Consumer, continually listening to the `chat_logs` topic, picks up the event.
    *   It formats and writes the structured data to a persistent shared volume (`chat-logs:/app/logs`) for future analytics and auditing.
