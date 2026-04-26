#!/bin/bash
# run_demo.sh: Script to set up the local environment and run a sample data feed

echo "Starting Docker Compose services..."
docker-compose up --build -d

echo "Waiting for backend to be healthy (approx 30s)..."
for i in {1..15}; do
  if curl -s http://localhost:8000/health | grep -q "status"; then
    echo "Backend is up!"
    break
  fi
  sleep 2
done

echo "Running sample data feed (simulating customer interactions)..."

# Sample 1: Greeting
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, I need help", "user_id": "demo_user", "lang": "en"}'
echo -e "\n"

# Sample 2: Order Tracking
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Where is my order? It is ORD-12345", "user_id": "demo_user", "lang": "en"}'
echo -e "\n"

# Sample 3: FAQ
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is your refund policy?", "user_id": "demo_user", "lang": "en"}'
echo -e "\n"

# Sample 4: Escalation / Negative Sentiment
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "This is terrible service, I want to talk to a human!", "user_id": "demo_user", "lang": "en"}'
echo -e "\n"

echo "Demo complete! You can view analytics at http://localhost:8000/analytics"
echo "To stop services, run: docker-compose down"
