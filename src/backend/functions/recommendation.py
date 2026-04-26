import logging

logger = logging.getLogger(__name__)

# Lightweight product catalog for deterministic recommendations.
PRODUCTS = {
    "laptop": [
        {
            "name": "ThinkPad X1 Carbon Gen 10",
            "price": "$1200",
            "type": "productivity",
            "keywords": {"business", "work", "office", "lightweight", "battery"},
        },
        {
            "name": "MacBook Pro M2 14-inch",
            "price": "$1999",
            "type": "creative",
            "keywords": {"creative", "design", "video", "editing", "mac"},
        },
        {
            "name": "Alienware m15 R7",
            "price": "$1800",
            "type": "gaming",
            "keywords": {"gaming", "games", "performance", "powerful"},
        },
    ],
    "phone": [
        {
            "name": "iPhone 14 Pro",
            "price": "$999",
            "type": "premium",
            "keywords": {"iphone", "ios", "camera", "premium"},
        },
        {
            "name": "Samsung Galaxy S23 Ultra",
            "price": "$1199",
            "type": "flagship",
            "keywords": {"android", "battery", "camera", "flagship"},
        },
        {
            "name": "Google Pixel 7 Pro",
            "price": "$899",
            "type": "smart",
            "keywords": {"android", "ai", "assistant", "camera", "value"},
        },
    ],
}


def _choose_category(text_lower: str) -> str:
    if any(word in text_lower for word in ["laptop", "computer", "mac", "notebook"]):
        return "laptop"
    return "phone"


def _score_product(product: dict, text_lower: str) -> int:
    score = 0
    if product.get("type") and product["type"] in text_lower:
        score += 3
    for keyword in product.get("keywords", set()):
        if keyword in text_lower:
            score += 2
    return score


def lambda_handler(event, context=None):
    """
    Simulates an AWS Lambda / Cloud Function.
    This is stateless, spin-up-on-demand logic.
    
    event mapping:
    {
        "entities": ["laptop", "gaming"], # Extracted from NLP
        "user_id": "user_123"
    }
    """
    try:
        entities = event.get("entities", [])
        text_lower = " ".join(entities).lower()
        target = _choose_category(text_lower)

        recommendations = PRODUCTS.get(target, PRODUCTS["phone"])
        rec = max(recommendations, key=lambda product: _score_product(product, text_lower))
        fit_reason = rec.get("type", target)
        response_text = (
            f"Based on what you asked, I recommend the {rec['name']} at {rec['price']}. "
            f"It is the best fit for {fit_reason} needs in our catalog."
        )

        return {
            "statusCode": 200,
            "body": {
                "recommendation": rec,
                "message": response_text,
            },
        }
    except Exception as e:
        logger.error(f"Lambda Error: {e}")
        return {
            "statusCode": 500,
            "body": {
                "message": "I experienced an error fetching recommendations right now.",
            },
        }

# For local testing if executed directly
if __name__ == "__main__":
    print(lambda_handler({"entities": ["laptop"]}))
