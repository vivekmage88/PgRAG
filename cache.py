import os
import json
import hashlib
import redis
from dotenv import load_dotenv

load_dotenv()

redis_client = redis.Redis(
    host="localhost",
    port=6379,
    db=3,
    decode_responses=True,
    socket_timeout=2,
    socket_connect_timeout=2,
)

EMBEDDING_TTL = 60 * 60 * 24 * 7    # 7 days
ANSWER_TTL = 60 * 60                # 1 hour


def make_key(prefix: str, value: str) -> str:
    normalised = value.strip().lower()
    digest = hashlib.sha256(normalised.encode()).hexdigest()
    return f"{prefix}:{digest[:32]}"


def get_cached_embedding(text: str) -> list[float] | None:
    try:
        raw = redis_client.get(make_key("embed", text))
        if raw is None:
            return None
        return json.loads(raw)
    except redis.RedisError as e:
        print(f"Redis read failed: {e}")
        return None


def set_cached_embedding(text: str, vector: list[float]) -> None:
    try:
        redis_client.set(make_key("embed", text), json.dumps(vector), ex=EMBEDDING_TTL)
    except redis.RedisError as e:
        print(f"Redis write failed: {e}")
        
        
# Cache for Answer Section

def make_answer_key(question: str, k: int, max_distance: float, document_id: int | None) -> str:
    payload = json.dumps(
        {
            "question": question.strip().lower(),
            "k": k,
            "max_distance": max_distance,
            "document_id": document_id,
        },
        sort_keys=True,
    )
    return make_key("answer", payload)


def get_cached_answer(question: str, k: int, max_distance: float,
    document_id: int | None) -> dict | None:
    try:
        raw = redis_client.get(make_answer_key(question, k, max_distance, document_id))
        if raw is None:
            return None
        return json.loads(raw)
    except redis.RedisError as e:
        print(f"Redis read failed: {e}")
        return None


def set_cached_answer(question: str, k: int, max_distance: float,
    document_id: int | None, result: dict) -> None:
    try:
        key = make_answer_key(question, k, max_distance, document_id)
        redis_client.set(key, json.dumps(result), ex=ANSWER_TTL)
    except redis.RedisError as e:
        print(f"Redis write failed: {e}")