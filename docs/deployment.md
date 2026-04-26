# Deployment Guide

This guide provides step-by-step instructions for deploying the Pro-Grade AI Assistant infrastructure using Docker Compose. The environment includes the frontend UI, backend API, NLP engine, messaging queues, and monitoring stack.

## Prerequisites

Before starting the deployment, ensure the host machine has the following installed:
*   **Docker Engine** (version 20.10.x or higher)
*   **Docker Compose** (version V2)
*   *Note: Ensure ports listed in the "Ports Explanation" section are not currently in use by other applications.*

---

## Step-by-Step Docker Setup

### 1. Clone the Repository
Ensure you are in the root directory of the project where the `docker-compose.yml` file is located:
```bash
git clone <repository_url>
cd cc-project-group10
```

### 2. Configure Environment Variables
Copy the example environment configuration (if provided) and adjust values as needed.
```bash
cp .env.example .env
```
*(The system is designed to run with default settings configured directly in `docker-compose.yml`, so this step is optional unless custom API keys or settings are needed).*

### 3. Build and Start the Infrastructure
Launch the entire stack in detached mode. This command will build the custom images for the React frontend, FastAPI backend, Java Lucene service, and the Python Kafka consumer, and then start all containers in the correct dependency order.
```bash
docker compose up -d --build
```

### 4. Verify the Deployment
Check the status of all running containers:
```bash
docker compose ps
```
Ensure all services report `Up (healthy)`. The infrastructure performs health checks automatically.

---

## Ports Explanation

The following ports are mapped to the host machine for access:

| Service | Host Port | Internal Port | Description |
| :--- | :--- | :--- | :--- |
| **Frontend** | `3000` | `3000` | The React User Interface. Access via `http://localhost:3000`. |
| **Grafana** | `3001` | `3000` | Monitoring Dashboards. Access via `http://localhost:3001`. |
| **Backend API** | `8000` | `8000` | FastAPI application. Access swagger docs at `http://localhost:8000/docs`. |
| **Prometheus** | `9090` | `9090` | Metrics Scraper/TSDB. Access via `http://localhost:9090`. |
| **Kafka** | `9092` | `9092` | Message Broker. Used for asynchronous logging. |
| **Lucene NLP** | `4567` | `4567` | Java OpenNLP microservice. Internal API layer for the backend. |
| **Redis** | `6379` | `6379` | In-memory datastore for user sessions and state management. |
| **Zookeeper** | `2181` | `2181` | Cluster coordinator for Kafka. |

---

## Troubleshooting Guide

### 1. Port Conflicts
**Symptom:** `Error starting userland proxy: listen tcp4 0.0.0.0:XXXX: bind: address already in use`
**Resolution:** Another process is using the required port. Identify the process (`lsof -i :XXXX` or `netstat -ano | findstr :XXXX` on Windows) and stop it, or modify the host port mapping in the `docker-compose.yml` (e.g., `"8080:8000"`).

### 2. Container Fails to Become 'Healthy'
**Symptom:** `docker compose ps` shows a container status as `unhealthy` or constantly restarting.
**Resolution:**
1.  Check the specific service logs to identify the crash reason:
    ```bash
    docker compose logs <service_name>
    ```
2.  If the **Backend** is unhealthy, it is likely waiting for **Kafka** or **Lucene** to boot. Give it a few more seconds, as the restart policy will automatically retry.

### 3. Missing Chat Logs / Analytics Empty
**Symptom:** The frontend analytics dashboard shows no data, or logs aren't appearing.
**Resolution:**
1.  Verify the `consumer` service is running: `docker compose logs consumer`.
2.  Check if the Kafka topic was successfully created. The `kafka` service logs should confirm `chat_logs:1:1` was initialized.
3.  Ensure the shared volume `chat-logs` is correctly mounted to both the `backend` and `consumer`.

### 4. High Resource Usage (Memory/CPU)
**Symptom:** The host machine is struggling, or containers are being OOM (Out of Memory) killed.
**Resolution:** The Java Lucene engine and Kafka broker require significant memory. Ensure your Docker Desktop / Docker Engine is allocated at least **4GB of RAM** and **2+ CPU cores**.

### 5. Rebuilding After Code Changes
If you modify source code in `/src/frontend`, `/src/backend`, or `/src/ai-chatbot`, you must rebuild the specific container:
```bash
docker compose up -d --build <service_name>
```
