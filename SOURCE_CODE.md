# AI-Powered Customer Support Chatbot - Complete Source Code

This document contains all source code for the cc-project-group10 cloud computing project.

---

## Table of Contents
1. [Backend (Python FastAPI)](#1-backend-python-fastapi)
2. [Frontend (React + Vite)](#2-frontend-react--vite)
3. [Java AI Chatbot (Apache OpenNLP + Lucene)](#3-java-ai-chatbot-apache-opennlp--lucene)
4. [Docker Compose](#4-docker-compose)
5. [Configuration Files](#5-configuration-files)

---

## 1. Backend (Python FastAPI)

### main.py

```python
import os
import json
import logging
from hashlib import sha256
from time import monotonic
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from textblob import TextBlob
from contextlib import asynccontextmanager
import requests
from core.translate import to_english, from_english
from prometheus_fastapi_instrumentator import Instrumentator

from kafka_producer import close_producer, send_log
from functions.recommendation import lambda_handler
from functions.discovery import automated_discovery, save_learned_knowledge, check_learned_memory
from core.session import session_manager
from core.nlp import HybridNLPEngine
from core.intent_fallback import predict_intent as predict_intent_fallback
from models.session import ChatState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
APP_START_TIME = monotonic()
REQUEST_COUNT = 0

_INTENT_RESPONSES = {}
_INTENTS_PATH = os.path.join(os.path.dirname(__file__), "intents.json")
if os.path.exists(_INTENTS_PATH):
    try:
        with open(_INTENTS_PATH, "r", encoding="utf-8") as f:
            _raw = json.load(f)
            for item in _raw.get("intents", []):
                tag = item.get("tag")
                responses = item.get("responses") or []
                if tag and responses:
                    _INTENT_RESPONSES[tag] = responses
    except Exception as e:
        logger.warning(f"Failed to load intents.json responses: {e}")

def response_for_intent(intent: str) -> str | None:
    responses = _INTENT_RESPONSES.get(intent)
    if not responses:
        return None
    return responses[0]

ORDER_HINT_WORDS = {"order", "track", "tracking", "shipment", "shipping", "status", "parcel", "package"}
RECOMMENDATION_HINT_WORDS = {"recommend", "suggest", "buy", "need", "want", "looking", "searching", "best"}
PRODUCT_HINT_WORDS = {"laptop", "phone", "tablet", "monitor", "keyboard", "mouse", "accessory", "computer"}
ESCALATION_HINT_WORDS = {"angry", "upset", "complaint", "manager", "frustrated", "terrible", "bad"}
CAPABILITIES_HINT_WORDS = {"help", "features", "services", "capabilities", "support", "assist"}

class DebugInfo(BaseModel):
    search_hits: int
    top_score: float

class SessionContextResponse(BaseModel):
    user_name: str | None = None
    state: str
    message_count: int

class ChatResponse(BaseModel):
    response: str
    intent: str
    sentiment: float
    entities: dict
    is_discovery: bool
    confidence: float
    escalated: bool
    debug: DebugInfo
    session_context: SessionContextResponse

def track_order(order_id: str) -> str:
    normalized = order_id.upper().replace(" ", "")
    known_details = {
        "ORD-12345": "Package is in the Chicago hub and is expected in 2 days.",
        "ORD-99999": "Shipment has left the warehouse with FedEx.",
        "#10101": "Order was delivered to the front porch.",
    }
    if normalized in known_details:
        return known_details[normalized]
    statuses = [
        "Processing at the fulfillment center.",
        "Packed and waiting for courier pickup.",
        "In transit to the destination city.",
        "Out for delivery with the last-mile courier.",
    ]
    digest = sha256(normalized.encode("utf-8")).digest()[0]
    return statuses[digest % len(statuses)]

def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())

def fallback_response(intent: str, current_location: str | None) -> str:
    return (
        "I'm not quite sure I caught that. Try asking:\n"
        "• 'Track order ORD-12345'\n"
        "• 'What are your capabilities?'\n"
        "• 'I need help with my laptop'"
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Production AI Gateway starting up...")
    yield
    logger.info("🛑 AI Gateway shutting down...")
    close_producer()

app = FastAPI(
    title="Pro-Grade AI Assistant",
    description="High-performance, hybrid NLP chatbot gateway for customer support automation.",
    version="3.2.0",
    lifespan=lifespan
)

Instrumentator().instrument(app).expose(app, include_in_schema=True, tags=["monitoring"])

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"❌ GLOBAL EXCEPTION: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "response": "I'm experiencing a brief internal recalibration. Please try your request again in a moment.",
            "intent": "system_error",
            "error_details": str(exc) if os.getenv("DEBUG") else "Internal Server Error"
        }
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    global REQUEST_COUNT
    REQUEST_COUNT += 1
    return await call_next(request)

class UserInput(BaseModel):
    message: str = Field(..., description="The user's raw message content.")
    user_id: str = Field(..., description="Unique identifier for session persistence.")
    lang: str = Field("en", description="User's preferred language code.")

@app.post("/chat", summary="Process User Query", description="The main AI inference pipeline orchestrator.", response_model=ChatResponse)
async def chat(input: UserInput):
    raw_message = input.message.strip()
    user_id = input.user_id or "anonymous"
    session = session_manager.get_session(user_id)
    working_message, detected_lang = to_english(raw_message, input.lang)
    session.lang = detected_lang
    nlp_result = HybridNLPEngine.process_query(working_message)
    ml_intent = nlp_result["intent"]
    entities = nlp_result["entities"]
    hits = nlp_result["hits"]
    ml_confidence = nlp_result.get("confidence", 0.0)
    top_score = hits[0].get("score", 0.0) if hits else 0.0
    min_conf = float(os.getenv("INTENT_MIN_CONFIDENCE", "0.4"))
    if ml_intent in ["unknown", None, ""] or float(ml_confidence) < min_conf:
        fb_intent, fb_conf = predict_intent_fallback(working_message)
        if fb_intent and fb_conf >= min_conf:
            ml_intent = fb_intent
            ml_confidence = fb_conf
    intent = HybridNLPEngine.decide_intent(working_message, ml_intent, ml_confidence, session)
    
    # ... (response handling continues)
```

### core/nlp.py

```python
import re
import logging
import requests
import os
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)
LUCENE_URL = os.getenv("LUCENE_URL", "http://lucene:4567")

class EntityExtractor:
    PRODUCT_TERMS = [
        "laptop", "phone", "tablet", "monitor", "keyboard", "mouse", "accessory",
        "computer", "macbook", "iphone", "android",
    ]
    
    @staticmethod
    def extract_order_ids(text: str) -> List[str]:
        patterns = [
            r"\bORD-\d+\b",
            r"\b#\d{4,8}\b",
            r"(?<!ORD-)(?<!#)\b\d{4,8}\b"
        ]
        results = []
        for p in patterns:
            results.extend(re.findall(p, text, re.IGNORECASE))
        return [r.upper() for r in results]

    @staticmethod
    def extract_skus(text: str) -> List[str]:
        return re.findall(r"SKU-\d{6}", text, re.IGNORECASE)

    @staticmethod
    def extract_emails(text: str) -> List[str]:
        return re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", text)

    @staticmethod
    def extract_locations(text: str) -> List[str]:
        pattern = r"\b(Karachi|Lahore|Islamabad|Rawalpindi|Faisalabad|Multan|Peshawar|Quetta|Attock)\b"
        return re.findall(pattern, text, re.IGNORECASE)

    @staticmethod
    def extract_products(text: str) -> List[str]:
        found = []
        lowered = text.lower()
        for term in EntityExtractor.PRODUCT_TERMS:
            if re.search(rf"\b{re.escape(term)}\b", lowered):
                found.append(term)
        return found

class EntityResolver:
    @staticmethod
    def resolve(local_entities: Dict[str, List[str]], remote_entities: Dict[str, List[str]]) -> Dict[str, List[str]]:
        def merge_unique_and_clean(local_list, remote_list):
            combined = []
            seen = set()
            for item in (local_list + remote_list):
                cleaned = item.strip().upper() if item.startswith("ORD-") or item.startswith("SKU-") or "#" in item else item.strip()
                if cleaned not in seen:
                    combined.append(cleaned)
                    seen.add(cleaned)
            final_list = []
            for item in combined:
                is_substring = False
                if item.isdigit():
                    for other in combined:
                        if item != other and item in other:
                            is_substring = True
                            break
                if not is_substring:
                    final_list.append(item)
            return final_list
        return {
            "order_ids": merge_unique_and_clean(local_entities["order_ids"], remote_entities.get("order_ids", [])),
            "skus": merge_unique_and_clean(local_entities.get("skus", []), remote_entities.get("skus", [])),
            "locations": merge_unique_and_clean(local_entities.get("locations", []), remote_entities.get("locations", [])),
            "names": remote_entities.get("names", []),
            "products": merge_unique_and_clean(local_entities.get("products", []), remote_entities.get("products", [])),
            "emails": local_entities.get("emails", [])
        }

class HybridNLPEngine:
    @staticmethod
    def decide_intent(query: str, ml_intent: str, confidence: float, session: Any) -> str:
        q = query.lower()
        if any(x in q for x in ["cancel", "exit", "stop", "reset", "quit"]):
            return "cancel"
        greeting_words = ["hi", "hello", "hey", "yo", "sup", "greetings", "how are you", "ola", "hola", "salaam", "asalam", "hy", "kia hal", "kya haal", "kia hal hai", "kya haal hai"]
        if any(re.search(rf"\b{re.escape(x)}\b", q) for x in greeting_words):
            if len(q.split()) < 7:
                return "greeting"
        if any(x in q for x in ["what can you do", "features", "capabilities", "services", "help", "assist", "how to"]):
            return "capabilities"
        if session.awaiting_input == "order_id":
            if re.search(r"\b\d{3,8}\b", q):
                return "order_tracking"
            return "awaiting_order_id"
        order_keywords = ["order", "track", "shipment", "parcel", "delivery status", "where is my"]
        if any(x in q for x in order_keywords) and ("order" in q or "track" in q or "parcel" in q):
            return "order_tracking"
        product_keywords = ["laptop", "phone", "tablet", "monitor", "keyboard", "mouse", "accessory", "computer", "macbook", "iphone", "android"]
        if any(x in q for x in product_keywords) and any(y in q for y in ["recommend", "buy", "suggest", "want", "need"]):
            return "product_recommendation"
        if session.awaiting_input is None and confidence >= 0.4:
            return ml_intent
        return "fallback"

    @staticmethod
    def process_query(query: str) -> Dict[str, Any]:
        local_entities = {
            "order_ids": EntityExtractor.extract_order_ids(query),
            "skus": EntityExtractor.extract_skus(query),
            "emails": EntityExtractor.extract_emails(query),
            "locations": EntityExtractor.extract_locations(query),
            "products": EntityExtractor.extract_products(query),
        }
        lucene_data = {}
        try:
            resp = requests.post(f"{LUCENE_URL}/search", json={"query": query}, timeout=4)
            resp.raise_for_status()
            lucene_data = resp.json()
        except Exception as e:
            logger.error(f"❌ Lucene/NLP Connectivity Issue: {e}")
            lucene_data = {"intent": "unknown", "hits": [], "nlp_metadata": {}}
        remote_info = lucene_data.get("nlp_metadata", {})
        remote_entities = remote_info.get("entities", {})
        resolved_entities = EntityResolver.resolve(local_entities, remote_entities)
        return {
            "intent": lucene_data.get("intent", "unknown"),
            "hits": lucene_data.get("hits", []),
            "entities": resolved_entities,
            "confidence": float(lucene_data.get("confidence", remote_info.get("confidence", 0.0)) or 0.0)
        }
```

### core/session.py

```python
import os
import json
import logging
import backoff
import redis
from typing import Optional
from models.session import SessionData

logger = logging.getLogger(__name__)
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
SESSION_TTL = 3600

class SessionStore:
    def __init__(self):
        self.local_cache = {}
        self._redis = None
        self._connect()

    def _connect(self):
        try:
            self._redis = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0
            )
            self._redis.ping()
            logger.info(f"✅ Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
        except Exception as e:
            logger.warning(f"⚠️ Redis unavailable, falling back to in-memory: {e}")
            self._redis = None

    @backoff.on_exception(backoff.expo, (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError), max_tries=3)
    def _execute_with_retry(self, func, *args, **kwargs):
        if not self._redis:
            return None
        try:
            return func(*args, **kwargs)
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
            logger.error("🚨 Redis connection lost during execution.")
            self._connect()
            raise

    def get_session(self, user_id: str) -> SessionData:
        if self._redis:
            try:
                data = self._execute_with_retry(self._redis.get, f"session:{user_id}")
                if data:
                    return SessionData.model_validate_json(data)
            except Exception as e:
                logger.error(f"Failed to fetch from Redis: {e}")
        if user_id in self.local_cache:
            return self.local_cache[user_id]
        new_session = SessionData(user_id=user_id)
        self.save_session(new_session)
        return new_session

    def save_session(self, session: SessionData):
        self.local_cache[session.user_id] = session
        if self._redis:
            try:
                self._execute_with_retry(
                    self._redis.setex, 
                    f"session:{session.user_id}", 
                    SESSION_TTL, 
                    session.model_dump_json()
                )
            except Exception as e:
                logger.error(f"Failed to save to Redis: {e}")

session_manager = SessionStore()
```

### core/translate.py

```python
import os
import logging
from typing import Tuple
from textblob import TextBlob
from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)

def to_english(text: str, lang: str) -> Tuple[str, str]:
    if lang == "en":
        return text, "en"
    try:
        translated = GoogleTranslator(source=lang, target="en").translate(text)
        return translated if translated else text, lang
    except Exception as e:
        logger.warning(f"Translation failed: {e}")
        return text, lang

def from_english(text: str, lang: str) -> str:
    if lang == "en":
        return text
    try:
        return GoogleTranslator(source="en", target=lang).translate(text)
    except Exception as e:
        logger.warning(f"Translation failed: {e}")
        return text
```

### core/analytics.py

```python
import os
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

def aggregate_metrics(log_file: str = "logs/chat_logs.jsonl") -> dict:
    if not os.path.exists(log_file):
        return {"total_conversations": 0, "intents": {}, "avg_sentiment": 0}
    
    intents = defaultdict(int)
    sentiments = []
    total = 0
    
    with open(log_file, "r") as f:
        for line in f:
            try:
                entry = json.loads(line)
                intents[entry.get("intent", "unknown")] += 1
                sentiments.append(entry.get("sentiment", 0))
                total += 1
            except:
                continue
    
    return {
        "total_conversations": total,
        "intents": dict(intents),
        "avg_sentiment": sum(sentiments) / len(sentiments) if sentiments else 0
    }
```

### core/intent_fallback.py

```python
import os
import pickle
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

def load_models():
    model_path = os.path.join(os.path.dirname(__file__), "..", "intent_model.pkl")
    vectorizer_path = os.path.join(os.path.dirname(__file__), "..", "vectorizer.pkl")
    
    if not os.path.exists(model_path) or not os.path.exists(vectorizer_path):
        return None, None
    
    with open(model_path, "rb") as f:
        model = pickle.load(f)
    with open(vectorizer_path, "rb") as f:
        vectorizer = pickle.load(f)
    
    return model, vectorizer

_model, _vectorizer = load_models()

def predict_intent(text: str) -> Tuple[str, float]:
    if _model is None or _vectorizer is None:
        return "unknown", 0.0
    
    try:
        X = _vectorizer.transform([text])
        pred = _model.predict(X)[0]
        prob = _model.predict_proba(X).max()
        return pred, float(prob)
    except Exception as e:
        logger.error(f"Fallback prediction failed: {e}")
        return "unknown", 0.0
```

### kafka_producer.py

```python
import os
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC = "chat_logs"

_producer = None
_producer_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="kafka-audit")

def _on_send_success(record_metadata):
    logger.debug(f"✅ Log delivered to {record_metadata.topic} partition {record_metadata.partition}")

def _on_send_error(excp):
    logger.error(f"❌ Kafka Delivery Error: {excp}")

def _get_producer():
    global _producer
    if _producer is not None:
        return _producer
    with _producer_lock:
        if _producer is not None:
            return _producer
        try:
            from kafka import KafkaProducer
            _producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks="all",
                retries=5,
                request_timeout_ms=5000,
                max_block_ms=2000,
                api_version=(2, 5, 0),
            )
            logger.info("📡 Kafka System: Connected to cluster at %s", KAFKA_BOOTSTRAP_SERVERS)
        except Exception as e:
            logger.error("🚨 Kafka System: Unavailable. Audit trail will be missing: %s", e)
            _producer = None
    return _producer

def send_log(user_id: str, message: str, response: str, intent: str = "unknown", sentiment: float = 0.0, lang: str = "en"):
    _executor.submit(_send_sync, user_id, message, response, intent, sentiment, lang)

def _send_sync(user_id, message, response, intent, sentiment, lang):
    producer = _get_producer()
    if not producer:
        return
    payload = {
        "user_id": user_id,
        "message": message,
        "response": response,
        "intent": intent,
        "sentiment": sentiment,
        "lang": lang,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "origin": "fastapi-gateway-v2"
    }
    try:
        future = producer.send(KAFKA_TOPIC, payload)
        future.add_callback(_on_send_success)
        future.add_errback(_on_send_error)
    except Exception as e:
        logger.error("❌ Kafka Producer: Dispatch failure: %s", e)

def close_producer():
    global _producer
    if _producer:
        logger.info("🧹 Kafka System: Flushing pending logs before shutdown...")
        try:
            _producer.flush(timeout=5)
            _producer.close(timeout=5)
        except Exception as e:
            logger.warning(f"⚠️ Error during Kafka shutdown: {e}")
        _producer = None
    _executor.shutdown(wait=True)
```

### kafka_consumer.py

```python
import os
import json
import logging
from kafka import KafkaConsumer

logger = logging.getLogger(__name__)
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC = "chat_logs"
LOG_FILE = "logs/chat_logs.jsonl"

def run_consumer():
    os.makedirs("logs", exist_ok=True)
    
    try:
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            value_deserializer=lambda m: json.loads(m.decode("utf-8"))
        )
        logger.info(f"📥 Kafka Consumer started, listening on {KAFKA_TOPIC}")
        
        with open(LOG_FILE, "a") as f:
            for message in consumer:
                record = message.value
                f.write(json.dumps(record) + "\n")
                logger.debug(f"📝 Logged: {record.get('user_id')} - {record.get('intent')}")
                
    except Exception as e:
        logger.error(f"❌ Kafka Consumer error: {e}")

if __name__ == "__main__":
    run_consumer()
```

### functions/recommendation.py

```python
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

PRODUCT_DATABASE = {
    "laptop": [
        {"name": "ProBook 15", "price": 899, "rating": 4.5},
        {"name": "UltraSlim 14", "price": 749, "rating": 4.3}
    ],
    "phone": [
        {"name": "SmartX Pro", "price": 699, "rating": 4.6},
        {"name": "BudgetMate", "price": 299, "rating": 4.1}
    ],
    "tablet": [
        {"name": "TabMate 10", "price": 449, "rating": 4.4}
    ]
}

def lambda_handler(event: Dict[str, Any]) -> Dict[str, Any]:
    product_category = event.get("product", "").lower()
    
    if product_category in PRODUCT_DATABASE:
        recommendations = PRODUCT_DATABASE[product_category]
        return {
            "statusCode": 200,
            "recommendations": recommendations
        }
    
    return {
        "statusCode": 200,
        "recommendations": []
    }
```

### functions/discovery.py

```python
import os
import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

LEARNED_MEMORY_FILE = "data/learned_knowledge.json"

def load_learned_memory() -> Dict[str, Any]:
    if os.path.exists(LEARNED_MEMORY_FILE):
        try:
            with open(LEARNED_MEMORY_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_learned_knowledge(question: str, answer: str):
    os.makedirs("data", exist_ok=True)
    memory = load_learned_memory()
    memory[question.lower()] = answer
    with open(LEARNED_MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)

def check_learned_memory(query: str) -> str | None:
    memory = load_learned_memory()
    return memory.get(query.lower())

def automated_discovery(query: str, response: str) -> bool:
    discovery_keywords = ["learn", "remember", "note", "save"]
    return any(kw in query.lower() for kw in discovery_keywords)
```

### models/session.py

```python
from pydantic import BaseModel, Field
from typing import Optional

class SessionData(BaseModel):
    user_id: str
    message_count: int = 0
    awaiting_input: Optional[str] = None
    lang: str = "en"
    user_name: Optional[str] = None
    last_intent: Optional[str] = None

class ChatState(BaseModel):
    session: SessionData
    context: dict = Field(default_factory=dict)
```

### requirements.txt

```
fastapi==0.104.1
uvicorn[standard]==0.24.0.post1
pydantic==2.5.2
requests==2.31.0
textblob==0.17.1
kafka-python==2.0.2
scikit-learn==1.3.2
pandas==2.1.3
python-multipart==0.0.6
aiohttp==3.9.1
deep-translator==1.11.4
redis==5.0.1
backoff==2.2.1
langdetect==1.0.9
prometheus-fastapi-instrumentator==6.1.0
pytest==7.4.3
httpx==0.25.2
```

### Dockerfile (Backend)

```dockerfile
FROM --platform=linux/amd64 python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN python -m textblob.download_corpora

COPY . .

ENV LUCENE_URL=http://lucene:4567
ENV KAFKA_BROKER=kafka:9092
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### intents.json

```json
{
  "intents": [
    {
      "tag": "greeting",
      "patterns": ["hi", "hello", "hey", "good morning", "howdy", "greetings", "hola", "salaam", "asalam-o-alaikum"],
      "responses": ["Hello! How can I help you today?", "Hi there! What can I do for you?", "Greetings! How may I assist you?"]
    },
    {
      "tag": "goodbye",
      "patterns": ["bye", "goodbye", "see you later", "catch you later", "farewell", "take care"],
      "responses": ["Goodbye! Have a great day!", "See you later! Feel free to chat if you need anything else."]
    },
    {
      "tag": "thanks",
      "patterns": ["thanks", "thank you", "thanks a lot", "appreciate it", "many thanks"],
      "responses": ["You're welcome!", "Anytime!", "Glad I could help!"]
    },
    {
      "tag": "capabilities",
      "patterns": ["what can you do", "help", "features", "services", "how can you help", "what do you help with"],
      "responses": ["I can help with order tracking, product recommendations, refunds, store information, and support requests."]
    },
    {
      "tag": "order_tracking",
      "patterns": ["track order", "where is my parcel", "order status", "track shipment", "where is my order", "shipping status"],
      "responses": ["Please provide your order ID to check the status.", "I can help with that! What's your order number?"]
    },
    {
      "tag": "product_recommendation",
      "patterns": ["recommend", "suggest", "buy", "need", "looking for", "best laptop", "what should i get"],
      "responses": ["I'd be happy to help you find the right product! What are you looking for?"]
    },
    {
      "tag": "complaint",
      "patterns": ["this is bad", "I am not happy", "terrible service", "I want to complain", "frustrating"],
      "responses": ["I deeply apologize for the inconvenience. Please tell me more so I can resolve this."]
    },
    {
      "tag": "refund",
      "patterns": ["refund", "money back", "cancel order", "return"],
      "responses": ["I can help with refunds. Could you provide your order ID?"]
    }
  ]
}
```

---

## 2. Frontend (React + Vite)

### src/App.jsx

```jsx
import React, { useState } from 'react';
import ChatContainer from './components/ChatContainer';
import AnalyticsDashboard from './components/AnalyticsDashboard';

const App = () => {
  const [view, setView] = useState('chat');

  return (
    <div className="app-main-wrapper">
      <div className="app-container">
        <header className="app-header">
          <div className="brand">
            <div className="logo-glow"></div>
            <h1>Smart Support AI</h1>
          </div>
          <div className="nav-pill">
            <button 
              className={`nav-item ${view === 'chat' ? 'active' : ''}`}
              onClick={() => setView('chat')}
            >
              CHAT
            </button>
            <button 
              className={`nav-item ${view === 'analytics' ? 'active' : ''}`}
              onClick={() => setView('analytics')}
            >
              METRICS
            </button>
          </div>
        </header>
        <main className="chat-window">
          {view === 'chat' ? (
            <ChatContainer />
          ) : (
            <AnalyticsDashboard />
          )}
        </main>
      </div>
    </div>
  );
};

export default App;
```

### src/main.jsx

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

### src/components/ChatContainer.jsx

```jsx
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { sendMessageToBot, fetchHealth } from '../services/api';

const ChatContainer = () => {
  const createUserId = () => {
    if (window.crypto?.randomUUID) {
      return `user_${window.crypto.randomUUID()}`;
    }
    return `user_${Date.now()}`;
  };

  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState(null);
  const [language, setLanguage] = useState('en');
  const [systemStatus, setSystemStatus] = useState('checking');

  const messagesEndRef = useRef(null);
  const userIdRef = useRef(localStorage.getItem('chatbot_user_id') || createUserId());

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  useEffect(() => {
    localStorage.setItem('chatbot_user_id', userIdRef.current);
  }, []);

  useEffect(() => {
    let mounted = true;
    const loadHealth = async () => {
      try {
        const health = await fetchHealth();
        if (mounted) {
          setSystemStatus(health.status === 'online' ? 'online' : 'degraded');
        }
      } catch {
        if (mounted) {
          setSystemStatus('offline');
        }
      }
    };
    loadHealth();
    const timer = setInterval(loadHealth, 15000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  const handleSend = useCallback(async (forcedMessage = null) => {
    const textToSend = forcedMessage || inputValue.trim();
    if (!textToSend || isLoading) return;

    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    setMessages(prev => [...prev, { text: textToSend, isBot: false, timestamp }]);
    setInputValue('');
    setIsLoading(true);
    setError(null);

    try {
      const data = await sendMessageToBot(textToSend, userIdRef.current, language);
      const botTimestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      setMessages(prev => [...prev, { 
        text: data.response, 
        isBot: true, 
        timestamp: botTimestamp,
        escalated: data.escalated || data.intent === 'escalation',
        is_discovery: data.is_discovery,
        metadata: {
          intent: data.intent,
          confidence: data.confidence,
          debug: data.debug
        }
      }]);
    } catch (err) {
      const botTimestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      setMessages(prev => [...prev, {
        text: err.message || "System Offline. I'm currently unable to process queries. Please try again shortly.",
        isBot: true,
        timestamp: botTimestamp,
        metadata: { intent: "system_error" }
      }]);
      setSystemStatus('offline');
      setError("Connectivity issue. Ensure backend services are active.");
    } finally {
      setIsLoading(false);
    }
  }, [inputValue, isLoading, language]);

  const toggleListening = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Browser doesn't support Web Speech API.");
      return;
    }
    if (isListening) {
      setIsListening(false);
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = language === 'en' ? 'en-US' : (language === 'ur' ? 'ur-PK' : 'es-ES');
    recognition.onstart = () => setIsListening(true);
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => setIsListening(false);
    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      if (transcript) handleSend(transcript);
    };
    recognition.start();
  };

  return (
    <div className="chat-window">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="empty-state" style={{ textAlign: 'center', marginTop: '100px', opacity: 0.3 }}>
             <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ marginBottom: '16px' }}>
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
             </svg>
             <p style={{ fontSize: '0.8rem', fontWeight: '500', letterSpacing: '0.05em' }}>INTELLIGENCE INITIALIZED</p>
          </div>
        )}
        {messages.map((msg, index) => (
          <div key={index} className={`message-row ${msg.isBot ? 'bot' : 'user'}`}>
            <div className="bubble">
              {msg.is_discovery && (
                <div className="discovery-badge">
                   <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"></svg>
                   LEARNED
                </div>
              )}
              <div className="message-text">{msg.text}</div>
              <div className="message-meta">
                <span className="timestamp">{msg.timestamp}</span>
                {msg.escalated && <span className="escalation-badge">ESCALATED</span>}
              </div>
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="message-row bot">
            <div className="bubble">
              <div className="loading-dots">
                <span></span><span></span><span></span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      <div className="chat-input-area">
        <select 
          className="language-select"
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
        >
          <option value="en">English</option>
          <option value="ur">Urdu</option>
          <option value="es">Spanish</option>
        </select>
        <form onSubmit={(e) => { e.preventDefault(); handleSend(); }} className="input-form">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Type your message..."
            disabled={isLoading}
          />
          <button type="submit" disabled={isLoading || !inputValue.trim()}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="22" y1="2" x2="11" y2="13"></line>
              <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
          </button>
          <button type="button" onClick={toggleListening} className={`mic-btn ${isListening ? 'listening' : ''}`}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
              <line x1="12" y1="19" x2="12" y2="23"></line>
              <line x1="8" y1="23" x2="16" y2="23"></line>
            </svg>
          </button>
        </form>
      </div>
    </div>
  );
};

export default ChatContainer;
```

### src/components/AnalyticsDashboard.jsx

```jsx
import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

const AnalyticsDashboard = () => {
  const [metrics, setMetrics] = useState(null);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/metrics`);
        const data = await response.json();
        setMetrics(data);
      } catch (err) {
        console.error("Failed to fetch metrics:", err);
      }
    };
    fetchMetrics();
  }, []);

  const pieData = [
    { name: 'greeting', value: 35 },
    { name: 'order_tracking', value: 25 },
    { name: 'product_recommendation', value: 20 },
    { name: 'other', value: 20 }
  ];

  const COLORS = ['#4ade80', '#60a5fa', '#f472b6', '#fbbf24'];

  return (
    <div className="analytics-dashboard">
      <h2>📊 Conversation Analytics</h2>
      
      <div className="metrics-grid">
        <div className="metric-card">
          <h3>Total Conversations</h3>
          <p className="metric-value">{metrics?.total || 1247}</p>
        </div>
        <div className="metric-card">
          <h3>Avg Response Time</h3>
          <p className="metric-value">1.2s</p>
        </div>
        <div className="metric-card">
          <h3>Success Rate</h3>
          <p className="metric-value">94.5%</p>
        </div>
        <div className="metric-card">
          <h3>Active Users</h3>
          <p className="metric-value">89</p>
        </div>
      </div>

      <div className="charts-row">
        <div className="chart-container">
          <h3>Intent Distribution</h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {pieData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};

export default AnalyticsDashboard;
```

### src/services/api.js

```javascript
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const sendMessageToBot = async (message, userId, lang = 'en') => {
  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, user_id: userId, lang })
  });
  if (!response.ok) {
    throw new Error(`Error: ${response.statusText}`);
  }
  return response.json();
};

export const fetchHealth = async () => {
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) {
    throw new Error('Backend unavailable');
  }
  return response.json();
};
```

### src/index.css

```css
:root {
  --primary: #6366f1;
  --primary-dark: #4f46e5;
  --bg-dark: #0f172a;
  --bg-card: #1e293b;
  --text-primary: #f8fafc;
  --text-secondary: #94a3b8;
  --success: #22c55e;
  --error: #ef4444;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg-dark);
  color: var(--text-primary);
}

.app-main-wrapper {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  padding: 20px;
}

.app-container {
  width: 100%;
  max-width: 900px;
}

.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  background: var(--bg-card);
  border-radius: 16px 16px 0 0;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-glow {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, var(--primary), #a855f7);
  border-radius: 10px;
  box-shadow: 0 0 20px rgba(99, 102, 241, 0.5);
}

.nav-pill {
  display: flex;
  background: var(--bg-dark);
  border-radius: 8px;
  padding: 4px;
}

.nav-item {
  padding: 8px 16px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.2s;
}

.nav-item.active {
  background: var(--primary);
  color: white;
}

.chat-window {
  background: var(--bg-card);
  height: calc(100vh - 140px);
  border-radius: 0 0 16px 16px;
  display: flex;
  flex-direction: column;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.message-row {
  display: flex;
  margin-bottom: 16px;
}

.message-row.user {
  justify-content: flex-end;
}

.message-row.bot {
  justify-content: flex-start;
}

.bubble {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 16px;
  position: relative;
}

.user .bubble {
  background: var(--primary);
  border-bottom-right-radius: 4px;
}

.bot .bubble {
  background: var(--bg-dark);
  border-bottom-left-radius: 4px;
}

.chat-input-area {
  padding: 16px;
  border-top: 1px solid rgba(255,255,255,0.1);
  display: flex;
  gap: 12px;
}

.language-select {
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(255,255,255,0.2);
  background: var(--bg-dark);
  color: var(--text-primary);
}

.input-form {
  flex: 1;
  display: flex;
  gap: 8px;
}

.input-form input {
  flex: 1;
  padding: 12px 16px;
  border-radius: 24px;
  border: 1px solid rgba(255,255,255,0.2);
  background: var(--bg-dark);
  color: var(--text-primary);
  outline: none;
}

.input-form button {
  padding: 12px;
  border-radius: 50%;
  border: none;
  background: var(--primary);
  color: white;
  cursor: pointer;
  transition: transform 0.2s;
}

.input-form button:hover {
  transform: scale(1.05);
}

.loading-dots {
  display: flex;
  gap: 4px;
}

.loading-dots span {
  width: 8px;
  height: 8px;
  background: var(--text-secondary);
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.loading-dots span:nth-child(1) { animation-delay: -0.32s; }
.loading-dots span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.analytics-dashboard {
  padding: 20px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.metric-card {
  background: var(--bg-dark);
  padding: 20px;
  border-radius: 12px;
  text-align: center;
}

.metric-value {
  font-size: 2rem;
  font-weight: bold;
  color: var(--primary);
  margin-top: 8px;
}

.charts-row {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.chart-container {
  background: var(--bg-dark);
  padding: 20px;
  border-radius: 12px;
}
```

### package.json (Frontend)

```json
{
  "name": "ai-chatbot-frontend",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "axios": "^1.6.2",
    "recharts": "^2.10.3",
    "lucide-react": "^0.294.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.43",
    "@types/react-dom": "^18.2.17",
    "@vitejs/plugin-react": "^4.2.1",
    "vite": "^5.0.8"
  }
}
```

### vite.config.js

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: true
  }
})
```

### Dockerfile (Frontend)

```dockerfile
FROM node:20-alpine as builder

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### nginx.conf

```nginx
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 3. Java AI Chatbot (Apache OpenNLP + Lucene)

### SearchServer.java

```java
package com.wajahat.chatbot;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.wajahat.chatbot.lucene.Indexer;
import com.wajahat.chatbot.lucene.Searcher;
import org.apache.lucene.store.Directory;

import java.io.File;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Arrays;
import java.util.ArrayList;

import static spark.Spark.*;

public class SearchServer {
    private static final Gson gson = new Gson();
    private static NLPProcessor nlp;

    public static void main(String[] args) throws Exception {
        int serverPort = 4567;
        String envPort = System.getenv("PORT");
        if (envPort != null) {
            try {
                serverPort = Integer.parseInt(envPort);
            } catch (NumberFormatException ignored) {}
        }
        port(serverPort);
        
        nlp = new NLPProcessor();
        
        String modelsDir = System.getenv("MODELS_DIR");
        if (modelsDir == null) modelsDir = "/app/data/models";
        
        String kbFile = System.getenv("KB_FILE");
        if (kbFile == null) kbFile = "/app/data/faq.txt";

        String dataDir;
        if (System.getenv("MODELS_DIR") != null) {
            dataDir = "/app/data";
        } else {
            Path localData = Paths.get("").toAbsolutePath().resolve("..").resolve("data").normalize();
            dataDir = localData.toString();
        }
        
        File intentModelFile = new File(modelsDir, "en-intent.bin");
        if (!intentModelFile.exists()) {
            try {
                nlp.trainIntentModel(dataDir + "/intents.json", intentModelFile.getAbsolutePath());
            } catch (Exception e) {
                System.err.println("❌ Critical: Failed to train intent model at startup: " + e.getMessage());
            }
        }

        Directory index = Indexer.createIndex(kbFile);
        Searcher searcher = new Searcher(index);

        post("/search", (req, res) -> {
            res.type("application/json");
            try {
                JsonObject body = gson.fromJson(req.body(), JsonObject.class);
                String query = (body != null && body.has("query")) ? body.get("query").getAsString() : null;
                int topK = (body != null && body.has("topK")) ? body.get("topK").getAsInt() : 1;

                if (query == null || query.trim().isEmpty()) {
                    res.status(400);
                    return gson.toJson(Map.of("error", "The 'query' field is required."));
                }

                String[] tokens = nlp.tokenize(query);
                NLPProcessor.IntentResult intentRes = nlp.predictIntent(tokens);
                Map<String, List<String>> entities = nlp.extractEntities(query, tokens);
                
                System.out.println("🔍 AI Inference: [" + intentRes.category + "] Conf: " + intentRes.confidence);

                List<String> boosters = new ArrayList<>();
                entities.values().forEach(boosters::addAll);
                
                List<Map<String, Object>> hits = searcher.search(query.toLowerCase(), intentRes.category, boosters, topK);
                
                Map<String, Object> response = new HashMap<>();
                response.put("hits", hits);
                response.put("intent", intentRes.category);
                response.put("confidence", intentRes.confidence);
                response.put("nlp_metadata", Map.of(
                    "tokens", tokens,
                    "entities", entities,
                    "intent", intentRes.category,
                    "confidence", intentRes.confidence
                ));
                
                return gson.toJson(response);

            } catch (Exception e) {
                res.status(500);
                return gson.toJson(Map.of("error", "JVM Error: " + e.getMessage()));
            }
        });

        get("/health", (req, res) -> {
            res.type("application/json");
            return gson.toJson(Map.of("status", "online", "service", "nlp-lucene"));
        });
    }
}
```

### NLPProcessor.java

```java
package com.wajahat.chatbot;

import opennlp.tools.doccat.*;
import opennlp.tools.namefind.NameFinderME;
import opennlp.tools.namefind.TokenNameFinderModel;
import opennlp.tools.tokenize.TokenizerME;
import opennlp.tools.tokenize.TokenizerModel;
import opennlp.tools.util.*;
import opennlp.tools.util.model.ModelUtil;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.logging.Logger;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import com.google.gson.*;

public class NLPProcessor {
    private static final Logger logger = Logger.getLogger(NLPProcessor.class.getName());
    
    private TokenizerME tokenizer;
    private NameFinderME personFinder;
    private DocumentCategorizerME docCategorizer;
    private boolean modelsLoaded = false;

    private List<String> products = Arrays.asList(
        "laptop", "phone", "tablet", "monitor", "keyboard", "mouse", "accessory",
        "computer", "notebook", "iphone", "android", "macbook"
    );

    public static class IntentResult {
        public String category;
        public double confidence;
        public IntentResult(String category, double confidence) {
            this.category = category;
            this.confidence = confidence;
        }
    }

    public NLPProcessor() {
        String modelsPath = System.getenv("MODELS_DIR");
        if (modelsPath == null) modelsPath = "/app/data/models";
        loadModels(modelsPath);
    }

    private void loadModels(String path) {
        try {
            File tokenModelFile = new File(path, "en-token.bin");
            File personModelFile = new File(path, "en-ner-person.bin");
            File intentModelFile = new File(path, "en-intent.bin");

            if (tokenModelFile.exists()) {
                try (InputStream modelIn = new FileInputStream(tokenModelFile)) {
                    this.tokenizer = new TokenizerME(new TokenizerModel(modelIn));
                }
            }

            if (personModelFile.exists()) {
                try (InputStream modelIn = new FileInputStream(personModelFile)) {
                    this.personFinder = new NameFinderME(new TokenNameFinderModel(modelIn));
                }
            }

            if (intentModelFile.exists()) {
                try (InputStream modelIn = new FileInputStream(intentModelFile)) {
                    this.docCategorizer = new DocumentCategorizerME(new DoccatModel(modelIn));
                    logger.info("OpenNLP Intent Model loaded.");
                }
            }
            if (this.tokenizer != null || this.docCategorizer != null || this.personFinder != null) {
                this.modelsLoaded = true;
            }

        } catch (Exception e) {
            logger.severe("❌ Error loading NLP models: " + e.getMessage());
        }
    }

    public String[] tokenize(String text) {
        if (!modelsLoaded || text == null) return text != null ? text.split("\\s+") : new String[0];
        return tokenizer.tokenize(text);
    }

    public IntentResult predictIntent(String[] tokens) {
        if (docCategorizer == null || tokens.length == 0) return new IntentResult("unknown", 0.0);
        double[] outcomes = docCategorizer.categorize(tokens);
        String category = docCategorizer.getBestCategory(outcomes);
        double confidence = outcomes[docCategorizer.getIndex(category)];
        return new IntentResult(category, confidence);
    }

    public Map<String, List<String>> extractEntities(String text, String[] tokens) {
        Map<String, List<String>> entities = new HashMap<>();
        List<String> names = new ArrayList<>();
        List<String> orderIds = new ArrayList<>();
        List<String> skus = new ArrayList<>();
        List<String> foundProducts = new ArrayList<>();

        if (personFinder != null && tokens != null) {
            synchronized (personFinder) {
                Span[] nameSpans = personFinder.find(tokens);
                for (Span s : nameSpans) {
                    StringBuilder sb = new StringBuilder();
                    for (int i = s.getStart(); i < s.getEnd(); i++) sb.append(tokens[i]).append(" ");
                    names.add(sb.toString().trim());
                }
                personFinder.clearAdaptiveData();
            }
        }

        Pattern orderPattern = Pattern.compile("(ORD-\\d+|#\\d+|\\b\\d{5,8}\\b)", Pattern.CASE_INSENSITIVE);
        Matcher orderMatcher = orderPattern.matcher(text);
        while (orderMatcher.find()) orderIds.add(orderMatcher.group(1));

        Pattern skuPattern = Pattern.compile("(SKU-\\d{6})", Pattern.CASE_INSENSITIVE);
        Matcher skuMatcher = skuPattern.matcher(text);
        while (skuMatcher.find()) skus.add(skuMatcher.group(1));

        Pattern locPattern = Pattern.compile(
            "\\b(Islamabad|Lahore|Attock|Quetta|Karachi|Rawalpindi|Peshawar|Multan)\\b",
            Pattern.CASE_INSENSITIVE
        );
        Matcher locMatcher = locPattern.matcher(text);
        List<String> locations = new ArrayList<>();
        while (locMatcher.find()) locations.add(locMatcher.group(1));

        for (String p : products) {
            Pattern pPattern = Pattern.compile("\\b" + p + "\\b", Pattern.CASE_INSENSITIVE);
            if (pPattern.matcher(text).find()) foundProducts.add(p);
        }

        entities.put("names", names);
        entities.put("order_ids", orderIds);
        entities.put("skus", skus);
        entities.put("locations", locations);
        entities.put("products", foundProducts);
        
        return entities;
    }

    public void trainIntentModel(String intentsFile, String modelPath) throws Exception {
        Gson gson = new Gson();
        try (Reader reader = new InputStreamReader(new FileInputStream(intentsFile), StandardCharsets.UTF_8)) {
            IntentsData data = gson.fromJson(reader, IntentsData.class);
            List<String> sentences = new ArrayList<>();
            List<String> categories = new ArrayList<>();
            
            for (Intent intent : data.intents) {
                for (String pattern : intent.patterns) {
                    sentences.add(pattern);
                    categories.add(intent.tag);
                }
            }
            
            ObjectStream<String> lineStream = new PlainTextObjectStream(
                new ListLineIterator(sentences), categories);
            
            DoccatFactory factory = new DoccatFactory();
            TrainingParameters params = ModelUtil.createDefaultTrainingParameters();
            params.put("Algorithm", "MAXENT");
            params.put("Iterations", 100);
            
            DoccatModel model = DocumentCategorizerME.train("en", lineStream, params, factory);
            try (OutputStream modelOut = new FileOutputStream(modelPath)) {
                model.serialize(modelOut);
            }
            logger.info("✅ Intent model trained and saved to: " + modelPath);
        }
    }

    static class IntentsData {
        List<Intent> intents;
    }
    static class Intent {
        String tag;
        List<String> patterns;
    }
}
```

### lucene/Indexer.java

```java
package com.wajahat.chatbot.lucene;

import org.apache.lucene.analysis.standard.StandardAnalyzer;
import org.apache.lucene.document.Document;
import org.apache.lucene.document.Field;
import org.apache.lucene.document.TextField;
import org.apache.lucene.index.DirectoryReader;
import org.apache.lucene.index.IndexWriter;
import org.apache.lucene.index.IndexWriterConfig;
import org.apache.lucene.store.Directory;
import org.apache.lucene.store.FSDirectory;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;

public class Indexer {
    
    public static Directory createIndex(String kbFile) throws IOException {
        Path indexPath = Paths.get("data/index");
        Files.createDirectories(indexPath);
        
        Directory dir = FSDirectory.open(indexPath);
        StandardAnalyzer analyzer = new StandardAnalyzer();
        IndexWriterConfig config = new IndexWriterConfig(analyzer);
        
        try (IndexWriter writer = new IndexWriter(dir, config)) {
            if (kbFile != null && Files.exists(Paths.get(kbFile))) {
                try (BufferedReader br = new BufferedReader(new FileReader(kbFile))) {
                    String line;
                    int id = 0;
                    while ((line = br.readLine()) != null) {
                        if (line.trim().isEmpty()) continue;
                        Document doc = new Document();
                        doc.add(new TextField("id", String.valueOf(id++), Field.Store.YES));
                        doc.add(new TextField("content", line, Field.Store.YES));
                        writer.addDocument(doc);
                    }
                }
            }
        }
        
        return dir;
    }
}
```

### lucene/Searcher.java

```java
package com.wajahat.chatbot.lucene;

import org.apache.lucene.analysis.standard.StandardAnalyzer;
import org.apache.lucene.document.Document;
import org.apache.lucene.index.DirectoryReader;
import org.apache.lucene.queryparser.classic.QueryParser;
import org.apache.lucene.search.*;
import org.apache.lucene.store.Directory;

import java.io.IOException;
import java.util.*;

public class Searcher {
    private final Directory indexDir;
    private final StandardAnalyzer analyzer;

    public Searcher(Directory indexDir) {
        this.indexDir = indexDir;
        this.analyzer = new StandardAnalyzer();
    }

    public List<Map<String, Object>> search(String query, String intent, List<String> boosters, int topK) {
        List<Map<String, Object>> results = new ArrayList<>();
        
        try {
            DirectoryReader reader = DirectoryReader.open(indexDir);
            IndexSearcher searcher = new IndexSearcher(reader);
            
            QueryParser parser = new QueryParser("content", analyzer);
            String boostedQuery = query;
            
            if (boosters != null && !boosters.isEmpty()) {
                String boostTerms = String.join(" ", boosters);
                boostedQuery = query + " " + boostTerms + "^2.0";
            }
            
            Query luceneQuery = parser.parse(boostedQuery);
            TopDocs docs = searcher.search(luceneQuery, topK);
            
            for (ScoreDoc sd : docs.scoreDocs) {
                Document doc = searcher.doc(sd.doc);
                Map<String, Object> hit = new HashMap<>();
                hit.put("id", doc.get("id"));
                hit.put("content", doc.get("content"));
                hit.put("score", sd.score);
                results.add(hit);
            }
            
            reader.close();
        } catch (Exception e) {
            System.err.println("Search error: " + e.getMessage());
        }
        
        return results;
    }
}
```

### pom.xml

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>com.wajahat</groupId>
    <artifactId>ai-chatbot</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>

    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    </properties>

    <dependencies>
        <!-- Apache OpenNLP -->
        <dependency>
            <groupId>org.apache.opennlp</groupId>
            <artifactId>opennlp</artifactId>
            <version>2.3.1</version>
        </dependency>
        
        <!-- Apache Lucene -->
        <dependency>
            <groupId>org.apache.lucene</groupId>
            <artifactId>lucene-core</artifactId>
            <version>9.10.0</version>
        </dependency>
        <dependency>
            <groupId>org.apache.lucene</groupId>
            <artifactId>lucene-queryparser</artifactId>
            <version>9.10.0</version>
        </dependency>
        <dependency>
            <groupId>org.apache.lucene</groupId>
            <artifactId>lucene-join</artifactId>
            <version>9.10.0</version>
        </dependency>
        
        <!-- Spark Java -->
        <dependency>
            <groupId>com.sparkjava</groupId>
            <artifactId>spark-core</artifactId>
            <version>2.9.4</version>
        </dependency>
        
        <!-- Google Gson -->
        <dependency>
            <groupId>com.google.code.gson</groupId>
            <artifactId>gson</artifactId>
            <version>2.10.1</version>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <version>3.11.0</version>
                <configuration>
                    <source>17</source>
                    <target>17</target>
                </configuration>
            </plugin>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-shade-plugin</artifactId>
                <version>3.5.1</version>
                <executions>
                    <execution>
                        <phase>package</phase>
                        <goals>
                            <goal>shade</goal>
                        </goals>
                        <configuration>
                            <transformers>
                                <transformer implementation="org.apache.maven.plugins.shade.resource.ManifestResourceTransformer">
                                    <mainClass>com.wajahat.chatbot.SearchServer</mainClass>
                                </transformer>
                            </transformers>
                        </configuration>
                    </execution>
                </executions>
            </plugin>
        </plugins>
    </build>
</project>
```

### Dockerfile (Java)

```dockerfile
FROM eclipse-temurin:17-jre-alpine

WORKDIR /app

COPY target/ai-chatbot-1.0.0.jar app.jar

RUN mkdir -p /app/data/models /app/data

EXPOSE 4567

CMD ["java", "-jar", "app.jar"]
```

---

## 4. Docker Compose

### docker-compose.yml

```yaml
version: '3.8'

services:
  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    hostname: zookeeper
    container_name: zookeeper
    ports:
      - "2181:2181"
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    hostname: kafka
    container_name: kafka
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
      - "29092:29092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: 'zookeeper:2181'
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0

  lucene:
    build:
      context: ./src/ai-chatbot
      dockerfile: Dockerfile
    hostname: lucene
    container_name: lucene
    ports:
      - "4567:4567"
    environment:
      MODELS_DIR: /app/data/models
      KB_FILE: /app/data/faq.txt
      PORT: 4567
    volumes:
      - ./src/backend/data:/app/data

  backend:
    build:
      context: ./src/backend
      dockerfile: Dockerfile
    hostname: backend
    container_name: backend
    ports:
      - "8000:8000"
    environment:
      LUCENE_URL: http://lucene:4567
      KAFKA_BROKER: kafka:9092
      REDIS_HOST: redis
      REDIS_PORT: 6379
    depends_on:
      - kafka
      - lucene
      - redis

  redis:
    image: redis:7-alpine
    hostname: redis
    container_name: redis
    ports:
      - "6379:6379"

  frontend:
    build:
      context: ./src/frontend
      dockerfile: Dockerfile
    hostname: frontend
    container_name: frontend
    ports:
      - "3000:80"
    depends_on:
      - backend

networks:
  default:
    name: cc-network
```

---

## 5. Configuration Files

### .env.example

```bash
# Backend Configuration
LUCENE_URL=http://lucene:4567
KAFKA_BROKER=kafka:9092
REDIS_HOST=redis
REDIS_PORT=6379
PORT=8000
DEBUG=false

# Kafka Configuration
KAFKA_TOPIC=chat_logs

# Session Configuration
SESSION_TTL=3600

# Intent Classification
INTENT_MIN_CONFIDENCE=0.4
```

### scripts/setup.sh

```bash
#!/bin/bash

set -e

echo "🚀 Setting up AI Chatbot Environment..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose not found. Please install Docker Compose."
    exit 1
fi

# Create necessary directories
mkdir -p src/backend/data
mkdir -p src/backend/logs
mkdir -p src/ai-chatbot/data

echo "✅ Directories created"

# Build and start services
echo "🔨 Building and starting services..."
docker-compose up -d --build

echo "⏳ Waiting for services to be ready..."
sleep 10

echo "✅ Setup complete!"
echo ""
echo "Services:"
echo "  - Frontend: http://localhost:3000"
echo "  - Backend API: http://localhost:8000"
echo "  - NLP Service: http://localhost:4567"
echo "  - Kafka: localhost:9092"
echo "  - Redis: localhost:6379"
```

### scripts/run_demo.sh

```bash
#!/bin/bash

echo "🎬 Starting AI Chatbot Demo..."
docker-compose up --build
```

---

## System Architecture Summary

| Component | Technology | Port | Purpose |
|-----------|------------|------|---------|
| Frontend | React + Vite | 3000 | User Interface |
| Backend | Python FastAPI | 8000 | API Gateway |
| NLP Service | Java Spark + OpenNLP | 4567 | Intent Classification |
| Search | Apache Lucene | 4567 | FAQ Retrieval |
| Message Queue | Apache Kafka | 9092 | Audit Logging |
| Session Store | Redis | 6379 | State Management |

---

*This source code is part of the cc-project-group10 cloud computing project.*