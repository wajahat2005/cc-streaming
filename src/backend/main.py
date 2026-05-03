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

# Internal modules
from kafka_producer import close_producer, send_log
from functions.recommendation import lambda_handler
from functions.discovery import automated_discovery, save_learned_knowledge, check_learned_memory
from core.session import session_manager
from core.nlp import HybridNLPEngine
from core.intent_fallback import predict_intent as predict_intent_fallback
from models.session import ChatState

# --- CONFIGURATION ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
APP_START_TIME = monotonic()

# Intent response bank for deterministic "smalltalk"/FAQ-style replies
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

# --- UTILITIES ---

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

# --- FASTAPI APP ---
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

# ─── PROMETHEUS METRICS ─────────────────────────────────────────────────────
# Auto-instruments all routes and exposes GET /metrics in Prometheus format.
Instrumentator().instrument(app).expose(app, include_in_schema=True, tags=["monitoring"])

# ─── PART 1: ROBUST ERROR HANDLING ─────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Senior-Grade Global Exception Handler: Captures all unhandled errors."""
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




class UserInput(BaseModel):
    message: str = Field(..., description="The user's raw message content.")
    user_id: str = Field(..., description="Unique identifier for session persistence.")
    lang: str = Field("en", description="User's preferred language code.")

# --- CORE ROUTE ---
@app.post("/chat", summary="Process User Query", description="The main AI inference pipeline orchestrator.", response_model=ChatResponse)
async def chat(input: UserInput):
    raw_message = input.message.strip()
    user_id = input.user_id or "anonymous"
    
    # 1. Load Session (Redis with Local Fallback)
    session = session_manager.get_session(user_id)
    
    # 2. Multilingual Support
    working_message, detected_lang = to_english(raw_message, input.lang)
    session.lang = detected_lang

    # 3. Hybrid Deterministic NLP Processing
    nlp_result = HybridNLPEngine.process_query(working_message)
    ml_intent = nlp_result["intent"]
    entities = nlp_result["entities"]
    hits = nlp_result["hits"]
    ml_confidence = nlp_result.get("confidence", 0.0)
    top_score = hits[0].get("score", 0.0) if hits else 0.0

    # Fallback to local model if Lucene/NLP is weak
    min_conf = float(os.getenv("INTENT_MIN_CONFIDENCE", "0.4"))
    if ml_intent in ["unknown", None, ""] or float(ml_confidence) < min_conf:
        fb_intent, fb_conf = predict_intent_fallback(working_message)
        if fb_intent and fb_conf >= min_conf:
            ml_intent = fb_intent
            ml_confidence = fb_conf

    # FINAL DETERMINISTIC DECISION (Locked Order 1-6)
    intent = HybridNLPEngine.decide_intent(working_message, ml_intent, ml_confidence, session)
    confidence = ml_confidence if intent == ml_intent else 1.0  # Rules have absolute confidence

    # 6. Personalization
    if entities["names"]:
        session.user_name = entities["names"][0]
    
    # 7. Response Generation
    response = "I encountered an internal processing issue."
    is_discovery = False
    is_escalated_response = False
    sentiment = float(TextBlob(working_message).sentiment.polarity)

    # 🇵🇰 Localized Contextual Targeting
    current_location = entities["locations"][0] if entities["locations"] else session.context.get("last_location")
    if entities["locations"]: 
        session.context["last_location"] = entities["locations"][0]

    if sentiment < -0.6:
        response = "I understand this is frustrating. I've flagged this for a senior specialist."
        session.escalated = True
        intent = "escalation"
        is_escalated_response = True
        session.clear_state()
    elif intent == "order_tracking":
        if entities["order_ids"]:
            order_id = entities["order_ids"][0]
            response = f"🔍 Status for {order_id}: {track_order(order_id)}"
            if current_location:
                response += f" (Destined for {current_location})"
            session.clear_state()
        else:
            session.awaiting_input = "order_id"
            session.active_flow = "order_tracking"
            session.state = ChatState.AWAITING_ORDER_ID
            response = "I'd like to help you track that. Please provide your Order ID (e.g., ORD-12345 or #12345)."
    elif intent == "capabilities":
        response = (
            "I'm your AI Support Assistant. Here's what I can do:\n"
            "• 📦 **Track Orders**: Check shipment status using your Order ID.\n"
            "• 🛒 **Product Help**: Ask about laptops, phones, and accessories.\n"
            "• 🇵🇰 **Local Support**: I specialize in Pakistani regions (Karachi, Lahore, etc.).\n"
            "• 👨‍💼 **Escalation**: I can connect you to a manager if things get tough."
        )
    elif intent == "greeting":
        response = response_for_intent("greeting") or "Hello! I'm your AI Support Assistant. How can I help you today?"
    elif intent == "goodbye":
        response = response_for_intent("goodbye") or "Goodbye! Have a great day!"
    elif intent == "thanks":
        response = response_for_intent("thanks") or "You're welcome! Happy to assist."
    elif intent == "cancel":
        session.clear_state()
        response = "Okay, I've reset our conversation. How else can I help you?"
    elif intent == "awaiting_order_id":
        response = "I'm still waiting for your Order ID (e.g., ORD-12345) to help you track that shipment. Or, you can say 'cancel' to stop."
    elif intent == "product_recommendation":
        event = {"entities": entities.get("products", []) + [working_message], "user_id": user_id}
        res = lambda_handler(event)
        response = res["body"]["message"]
        if current_location:
            response += f" We have express delivery available to {current_location}!"
    elif intent == "fallback":
        response = (
            "I'm not quite sure I caught that. Try asking:\n"
            "• 'Track order ORD-12345'\n"
            "• 'What are your capabilities?'\n"
            "• 'I need help with my laptop'"
        )
    else:
        # Prefer deterministic responses for common intents (prevents irrelevant Lucene FAQ matches)
        canned_intents = {
            "greeting",
            "goodbye",
            "thanks",
            "capabilities",
            "office_hours",
            "location",
            "payment_methods",
            "shipping_cost",
            "cancel_order",
            "refund_requests",
            "complaint",
        }
        if intent in canned_intents and confidence >= min_conf:
            canned = response_for_intent(intent)
            if canned:
                response = canned

        # Use Lucene hits only when they're strong enough (avoids answering the wrong thing)
        if response == "I encountered an internal processing issue." and hits:
            min_score = float(os.getenv("LUCENE_MIN_SCORE", "2.0"))
            hit_intent = (hits[0].get("intent") or "").lower()
            intent_l = (intent or "").lower()

            # Accept if: score is strong AND (intent matches OR intent is unknown OR intent confidence is low)
            if top_score >= min_score and (
                (hit_intent and hit_intent == intent_l)
                or intent_l == "unknown"
                or confidence < float(os.getenv("INTENT_LOW_CONFIDENCE", "0.25"))
            ):
                response = hits[0].get("content") or response

        if response == "I encountered an internal processing issue.":
            # Learned memory (local) first: if we already learned an answer, reuse it deterministically.
            learned = check_learned_memory(working_message)
            if learned:
                response = learned

            # Intelligent Fallback: Discovery
            disc = automated_discovery(working_message) if response == "I encountered an internal processing issue." else None
            if disc and response == "I encountered an internal processing issue.":
                response = f"I found this in our knowledge base: {disc['answer']}"
                save_learned_knowledge(working_message, disc['answer'])
                is_discovery = True
            else:
                response = fallback_response(intent, current_location)

    # 8. Save State & Audit
    session.add_message("user", raw_message)
    session.add_message("bot", response)
    session.last_intent = intent
    session_manager.save_session(session)
    
    send_log(user_id, raw_message, response, intent, sentiment, session.lang)

    # Translate response back to user's language (if enabled and non-English)
    response_out = from_english(response, session.lang)

    return {
        "response": response_out,
        "intent": intent,
        "sentiment": round(sentiment, 2),
        "entities": entities,
        "is_discovery": is_discovery,
        "confidence": round(confidence * 100, 1),
        "escalated": is_escalated_response,
        "debug": {
            "search_hits": len(hits),
            "top_score": round(top_score, 2) if hits else 0
        },
        "session_context": {
            "user_name": session.user_name,
            "state": session.state,
            "message_count": len(session.history)
        }
    }


@app.get("/health")
def health(): 
    lucene_ok = False
    try:
        lucene_resp = requests.get(f"{os.getenv('LUCENE_URL', 'http://lucene:4567')}/health", timeout=2)
        lucene_ok = lucene_resp.ok
    except Exception:
        lucene_ok = False

    storage_status = "redis" if session_manager._redis else "in-memory-fallback"
    status = "online" if lucene_ok else "degraded"
    return {
        "status": status,
        "session_storage": storage_status,
        "lucene_up": lucene_ok,
        "version": "3.2.0",
    }

@app.get("/analytics")
async def get_metrics():
    from core.analytics import AnalyticsEngine
    return AnalyticsEngine.get_metrics()



