# Chatbot Test Suite

This directory contains unit and integration tests for the AI-Powered Customer Support Chatbot.

## Directory Structure

```
tests/
├── unit/           # Unit tests for individual components
├── integration/    # Integration tests for system workflows
└── README.md       # This file
```

## Running Tests

### Unit Tests
```bash
cd src/backend
pytest test_chatbot_api.py -v
pytest test_analytics_aggregation.py -v
```

### Integration Tests
```bash
# Start services first
docker compose up -d

# Run integration tests
pytest tests/integration/ -v
```

## Test Coverage

- **API Tests**: Chat endpoint, health checks, error handling
- **Analytics Tests**: Log aggregation, metrics computation
- **NLP Tests**: Intent classification, entity extraction
- **Integration Tests**: End-to-end conversation flows

## Notes

- Backend tests are also available in `src/backend/` for convenience
- Integration tests require all services (Kafka, Redis, Lucene) to be running
- Use `docker compose up` to start all required services before running integration tests