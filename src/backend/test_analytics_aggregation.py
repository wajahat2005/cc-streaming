import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import os
import sys
import json

# Setup env for testing
os.environ["LOG_FILE"] = "backend/logs/chat_logs.jsonl"

# Mocking external dependencies removed to prevent breaking other tests.

# Now import the app
from main import app

client = TestClient(app)

class TestAnalytics:
    
    def test_analytics_aggregation(self):
        # Create a temporary log file (the one I created in command_status might not be reachable here)
        log_path = "backend/logs/chat_logs.jsonl"
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        
        test_data = [
            {"user_id": "u1", "intent": "greeting", "sentiment": 0.5, "timestamp": "2026-04-20T10:00:00Z", "lang": "en"},
            {"user_id": "u1", "intent": "order_tracking", "sentiment": 0.2, "timestamp": "2026-04-20T10:01:00Z", "lang": "en"},
            {"user_id": "u2", "intent": "escalation", "sentiment": -0.8, "timestamp": "2026-04-20T10:05:00Z", "lang": "ur"}
        ]
        
        with open(log_path, "w") as f:
            for entry in test_data:
                f.write(json.dumps(entry) + "\n")
        
        response = client.get("/analytics")
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 3
        assert data["intents"]["greeting"] == 1
        assert data["intents"]["escalation"] == 1
        assert data["escalations"] == 1
        assert data["avg_conv_length"] == 1.5 # 3 messages / 2 users
        assert data["languages"]["en"] == 2
        assert data["languages"]["ur"] == 1
        assert len(data["timeline"]) == 3

if __name__ == "__main__":
    pytest.main([__file__])
