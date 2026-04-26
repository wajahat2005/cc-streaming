import re
import logging
import requests
import os
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

LUCENE_URL = os.getenv("LUCENE_URL", "http://lucene:4567")

class EntityExtractor:
    """Native Python Regex Extractor for rigid patterns (Order IDs, SKUs, Emails)."""

    PRODUCT_TERMS = [
        "laptop",
        "phone",
        "tablet",
        "monitor",
        "keyboard",
        "mouse",
        "accessory",
        "computer",
        "macbook",
        "iphone",
        "android",
    ]
    
    @staticmethod
    def extract_order_ids(text: str) -> List[str]:
        """Safely extracts Order IDs using strict prefixes and numeric boundaries."""
        patterns = [
            r"\bORD-\d+\b",
            r"\b#\d{4,8}\b",
            r"(?<!ORD-)(?<!#)\b\d{4,8}\b"  # Raw numbers (4-8 digits)
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
        """🇵🇰 Targeted Location Regex for major Pakistani cities."""
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
    """Context-aware resolution and deduplication of entities."""
    
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
    """Orchestrates Python's rigid regex and Java's probabilistic NLP with a Deterministic Logic Engine."""
    
    @staticmethod
    def decide_intent(query: str, ml_intent: str, confidence: float, session: Any) -> str:
        """
        Final Deterministic Decision Engine (Locked Priority Order: 1-6).
        Enforces State Handling > Rules > ML Backup.
        """
        q = query.lower()
        
        # 🟢 1. CANCEL / RESET (High Priority)
        if any(x in q for x in ["cancel", "exit", "stop", "reset", "quit"]):
            return "cancel"

        # 🟢 2. GREETING (Non-Blocking)
        greeting_words = [
            "hi", "hello", "hey", "yo", "sup", "greetings", "how are you", 
            "ola", "hola", "salaam", "asalam", "hy", "kia hal", "kya haal", "kia hal hai", "kya haal hai"
        ]
        if any(re.search(rf"\b{re.escape(x)}\b", q) for x in greeting_words):
            if len(q.split()) < 7: # Keep it for short greetings only
                return "greeting"

        # 🟢 3. CAPABILITIES (Hard Intent)
        if any(x in q for x in ["what can you do", "features", "capabilities", "services", "help", "assist", "how to"]):
            return "capabilities"

        # 🟢 4. STATE HANDLING
        if session.awaiting_input == "order_id":
            if re.search(r"\b\d{3,8}\b", q):
                return "order_tracking"
            return "awaiting_order_id"

        # 🟢 5. ORDER DETECTION (Context Only)
        # Trigger tracking if keywords are present, even without a number (main.py will ask for it)
        order_keywords = ["order", "track", "shipment", "parcel", "delivery status", "where is my"]
        if any(x in q for x in order_keywords) and ("order" in q or "track" in q or "parcel" in q):
            return "order_tracking"

        # 🟢 5.5 PRODUCT DETECTION
        product_keywords = ["laptop", "phone", "tablet", "monitor", "keyboard", "mouse", "accessory", "computer", "macbook", "iphone", "android"]
        if any(x in q for x in product_keywords) and any(y in q for y in ["recommend", "buy", "suggest", "want", "need"]):
            return "product_recommendation"

        # 🟢 6. ML FALLBACK (Safe Mode Only)
        if session.awaiting_input is None and confidence >= 0.4:
            return ml_intent

        # 🟢 7. DEFAULT FALLBACK
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
