import json
import os
import difflib

def _resolve_data_dir() -> str:
    """
    Resolve a readable/writable data directory for both Docker and local dev.
    Docker: /app/data (volume mount)
    Local:  backend/data (repo-relative)
    """
    docker_dir = "/app/data"
    if os.path.isdir(docker_dir):
        return docker_dir

    here = os.path.dirname(os.path.abspath(__file__))
    local_dir = os.path.normpath(os.path.join(here, "..", "data"))
    if os.path.isdir(local_dir):
        return local_dir

    # Fallback to CWD (last resort)
    return os.getcwd()

DATA_DIR = _resolve_data_dir()
GLOBAL_DB = os.path.join(DATA_DIR, "global_knowledge.json")
LEARNED_DB = os.path.join(DATA_DIR, "learned_knowledge.json")

def automated_discovery(query):
    """
    Simulates a Cloud-based Automated Discovery (Web Search).
    Searches a 'Global' repository of knowledge to learn new answers.
    """
    if not os.path.exists(GLOBAL_DB):
        return None

    try:
        with open(GLOBAL_DB, "r", encoding="utf-8") as f:
            db = json.load(f)
            knowledge = db.get("global_knowledge", [])
            
            # Find the best match using string similarity (simulating search engine ranking)
            queries = [item["query"] for item in knowledge]
            matches = difflib.get_close_matches(query.lower(), queries, n=1, cutoff=0.6)
            
            if matches:
                item = next(i for i in knowledge if i["query"] == matches[0])
                return {
                    "answer": item["answer"],
                    "learned": True,
                    "source": "Global Cloud Discovery Service"
                }
    except Exception as e:
        print(f"Discovery Error: {e}")
        
    return None

def save_learned_knowledge(query, answer):
    """Persists learned information to the local learned database."""
    data = {}
    if os.path.exists(LEARNED_DB):
        try:
            with open(LEARNED_DB, "r") as f:
                data = json.load(f)
        except: pass
    
    data[query.lower()] = answer
    
    try:
        with open(LEARNED_DB, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Learning Error: {e}")

def check_learned_memory(query):
    """Checks if the bot has already learned this query."""
    if os.path.exists(LEARNED_DB):
        try:
            with open(LEARNED_DB, "r") as f:
                data = json.load(f)
                return data.get(query.lower())
        except: pass
    return None
