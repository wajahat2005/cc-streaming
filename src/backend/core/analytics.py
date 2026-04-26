import json
import os
import logging
from collections import Counter
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Path logic: Prioritize ENV, then fallback to Docker path, then local dev path
LOG_FILE = os.getenv("LOG_FILE", "/app/logs/chat_logs.jsonl")
if not os.path.exists(LOG_FILE) and os.path.exists("logs/chat_logs.jsonl"):
    LOG_FILE = "logs/chat_logs.jsonl"
elif not os.path.exists(LOG_FILE) and os.path.exists("backend/logs/chat_logs.jsonl"):
    LOG_FILE = "backend/logs/chat_logs.jsonl"

class AnalyticsEngine:
    """Production-grade log aggregator for bot metrics."""
    
    @staticmethod
    def get_metrics() -> Dict[str, Any]:
        default_stats = {
            "total": 0, 
            "intents": {}, 
            "avg_sentiment": 0, 
            "escalations": 0, 
            "accuracy": 1.0, 
            "avg_conv_length": 0,
            "languages": {}, 
            "timeline": []
        }
        
        if not os.path.exists(LOG_FILE):
            return default_stats

        logs: List[Dict[str, Any]] = []
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            logs.append(json.loads(line))
                        except:
                            continue # Skip corrupt lines
        except Exception as e:
            logger.error(f"Failed to read logs: {e}")
            return default_stats

        total = len(logs)
        if total == 0:
            return default_stats

        # 1. Intent Distribution
        intents = [log.get("intent", "unknown") for log in logs]
        intent_counts = Counter(intents)
        languages = Counter(log.get("lang", "en") for log in logs if log.get("lang"))

        # 2. Sentiment & Satisfaction Proxy
        sentiments = [log.get("sentiment", 0.0) for log in logs]
        avg_sentiment = sum(sentiments) / total

        # 3. Escalation Rate
        escalations = intent_counts.get("escalation", 0)
        
        # 4. Conversation Length (Avg messages per user)
        sessions: Dict[str, int] = Counter([log.get("user_id") for log in logs])
        avg_length = total / len(sessions) if sessions else 0

        # 5. Accuracy Proxy 
        # (Where intent is known and bot didn't fallback to discovery check)
        # Note: In a real system, this would be validated by user feedback
        successful_intents = total - intent_counts.get("unknown", 0)
        accuracy = successful_intents / total if total > 0 else 1.0

        # 6. Timeline (Last 20 points for trend)
        timeline = []
        for log in logs[-20:]:
            timeline.append({
                "t": log.get("timestamp", ""),
                "s": log.get("sentiment", 0.0),
                "i": log.get("intent", "unknown")
            })

        return {
            "total": total,
            "intents": dict(intent_counts),
            "avg_sentiment": round(avg_sentiment, 2),
            "escalations": escalations,
            "accuracy": round(accuracy, 2),
            "avg_conv_length": round(avg_length, 1),
            "languages": dict(languages),
            "timeline": timeline,
        }
