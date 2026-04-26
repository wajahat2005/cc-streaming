# Kubernetes Manifests

This directory contains Kubernetes manifests for deploying the chatbot system to a Kubernetes cluster.

## Contents

- `deployment.yaml` - Main deployment configuration
- `service.yaml` - Service definitions
- `ingress.yaml` - Ingress configuration
- `configmap.yaml` - Configuration
- `pvc.yaml` - Persistent volume claims

## Usage

```bash
# Apply all manifests
kubectl apply -f k8s/

# Check deployment status
kubectl get pods -l app=chatbot

# View logs
kubectl logs -l app=backend
```

## Prerequisites

- Kubernetes cluster (minikube, kind, or cloud provider)
- kubectl configured
- Container registry access for images

## Services

The manifests deploy:
- Frontend (React/Nginx)
- Backend (FastAPI)
- Lucene (Java NLP service)
- Kafka + Zookeeper
- Redis