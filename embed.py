import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EMBED_MODEL = "text-embedding-3-small"


def embed_texts(texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(model=EMBED_MODEL, input=texts)

    vectors = []
    for item in response.data:
        vectors.append(item.embedding)

    return vectors


def embed_in_batches(texts: list[str], batch_size: int = 50) -> list[list[float]]:
    all_vectors = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        vectors = embed_texts(batch)
        all_vectors.extend(vectors)
        print(f"embedded {len(all_vectors)}/{len(texts)}")

    return all_vectors