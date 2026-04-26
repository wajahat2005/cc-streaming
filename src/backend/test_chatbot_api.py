import json
import os
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

os.environ["ENABLE_TRANSLATION"] = "0"
os.environ["LOG_FILE"] = "backend/logs/chat_logs.jsonl"

from main import app
from core.session import session_manager


client = TestClient(app)


def _mock_lucene(intent="unknown", confidence=0.0, entities=None, hits=None):
    payload = {
        "intent": intent,
        "confidence": confidence,
        "hits": hits or [],
        "nlp_metadata": {
            "entities": entities
            or {
                "order_ids": [],
                "locations": [],
                "names": [],
                "skus": [],
                "products": [],
            },
            "confidence": confidence,
        },
    }
    response = Mock()
    response.json.return_value = payload
    return response


def _reset_session(user_id):
    session_manager.local_cache.pop(user_id, None)
    if session_manager._redis:
        try:
            session_manager._redis.delete(f"session:{user_id}")
        except Exception:
            pass


@patch("main.send_log")
@patch("core.nlp.requests.post")
def test_greeting_returns_greeting_response(mock_post, mock_send_log):
    user_id = "test_greeting"
    _reset_session(user_id)
    mock_post.return_value = _mock_lucene(intent="greeting", confidence=0.94)

    response = client.post("/chat", json={"message": "hello", "user_id": user_id, "lang": "en"})

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "greeting"
    assert "hello" in body["response"].lower() or "hi" in body["response"].lower()


@patch("main.send_log")
@patch("core.nlp.requests.post")
def test_order_tracking_without_id_asks_for_order_id(mock_post, mock_send_log):
    user_id = "test_order_prompt"
    _reset_session(user_id)
    mock_post.return_value = _mock_lucene(intent="order_tracking", confidence=0.93)

    response = client.post("/chat", json={"message": "where is my order", "user_id": user_id, "lang": "en"})

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "order_tracking"
    assert "order id" in body["response"].lower()
    assert body["session_context"]["state"] == "awaiting_order_id"


@patch("main.send_log")
@patch("core.nlp.requests.post")
def test_order_id_after_prompt_tracks_order(mock_post, mock_send_log):
    user_id = "test_order_id"
    _reset_session(user_id)
    mock_post.return_value = _mock_lucene(intent="order_tracking", confidence=0.9)
    client.post("/chat", json={"message": "where is my order", "user_id": user_id, "lang": "en"})

    mock_post.return_value = _mock_lucene(intent="unknown", confidence=0.1)
    response = client.post("/chat", json={"message": "12345", "user_id": user_id, "lang": "en"})

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "order_tracking"
    assert "12345" in body["response"]
    assert body["session_context"]["state"] == "idle"


@patch("main.send_log")
@patch("core.nlp.requests.post")
def test_product_query_returns_recommendation(mock_post, mock_send_log):
    user_id = "test_product"
    _reset_session(user_id)
    mock_post.return_value = _mock_lucene(
        intent="unknown",
        confidence=0.1,
        entities={"order_ids": [], "locations": [], "names": [], "skus": [], "products": ["laptop"]},
    )

    response = client.post("/chat", json={"message": "I want a laptop for gaming", "user_id": user_id, "lang": "en"})

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "product_recommendation"
    assert "recommend" in body["response"].lower()
    assert "alienware" in body["response"].lower()


@patch("main.send_log")
@patch("core.nlp.requests.post")
def test_negative_sentiment_escalates(mock_post, mock_send_log):
    user_id = "test_escalation"
    _reset_session(user_id)
    mock_post.return_value = _mock_lucene(intent="unknown", confidence=0.0)

    response = client.post("/chat", json={"message": "I am very angry", "user_id": user_id, "lang": "en"})

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "escalation"
    assert body["escalated"] is True
    assert "specialist" in body["response"].lower()


@patch("main.send_log")
@patch("core.nlp.requests.post")
def test_capabilities_query_returns_capabilities_response(mock_post, mock_send_log):
    user_id = "test_capabilities"
    _reset_session(user_id)
    mock_post.return_value = _mock_lucene(intent="unknown", confidence=0.2)

    response = client.post("/chat", json={"message": "what can you do", "user_id": user_id, "lang": "en"})

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "capabilities"
    assert "order" in body["response"].lower()
    assert "product" in body["response"].lower()


@patch("main.send_log")
@patch("core.nlp.requests.post")
def test_low_confidence_query_uses_fallback_response(mock_post, mock_send_log):
    user_id = "test_fallback"
    _reset_session(user_id)
    mock_post.return_value = _mock_lucene(intent="unknown", confidence=0.1)

    response = client.post("/chat", json={"message": "tell me something vague", "user_id": user_id, "lang": "en"})

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "fallback"
    assert "try asking" in body["response"].lower()


@patch("main.send_log")
@patch("core.nlp.requests.post")
def test_location_memory_enriches_follow_up(mock_post, mock_send_log):
    user_id = "test_location_memory"
    _reset_session(user_id)
    mock_post.return_value = _mock_lucene(intent="unknown", confidence=0.0)

    first = client.post("/chat", json={"message": "I am in Lahore", "user_id": user_id, "lang": "en"})
    assert first.status_code == 200

    mock_post.return_value = _mock_lucene(
        intent="unknown",
        confidence=0.0,
        entities={"order_ids": [], "locations": [], "names": [], "skus": [], "products": ["laptop"]},
    )
    second = client.post("/chat", json={"message": "recommend a laptop", "user_id": user_id, "lang": "en"})

    assert second.status_code == 200
    body = second.json()
    assert "Lahore" in body["response"]
