import os
from openai import OpenAI
from dotenv import load_dotenv
from retrieval import search
from cache import get_cached_answer, set_cached_answer


load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
CHAT_MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """You answer questions about a technical document.

Use only the context provided. Cite the page number for each claim, like (p17).
Answer from the context. Only say the document doesn't cover it if the context
is genuinely unrelated to the question."""

def build_context(matches):
    parts = []
    for chunk, distance in matches:
        parts.append(f"[Page {chunk.page} - {chunk.heading}]\n {chunk.content}")
    return "\n\n---\n\n".join(parts)

def generate_answer(question:str, context:str):
    completion = client.chat.completions.create(
        model = CHAT_MODEL,
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}
        ],
        temperature = 0.1,
        max_tokens = 400
    )
    return completion.choices[0].message.content

def answer_question(db, question: str, k: int = 5,max_distance: float = 0.6, document_id: int | None = None):
    answer_cached = get_cached_answer(question, k, max_distance, document_id)
    if answer_cached is not None:
        return answer_cached
    
    matches = search(db, question, k , max_distance, document_id)
    
    if not matches:
        result = {
            "answer": "I couldn't find anything in the document about that.",
            "sources": [],
        }
    else:
        context = build_context(matches)
        answer = generate_answer(question, context)
        
        sources = []
        for chunk, distance in matches:
            sources.append({
                "page": chunk.page,
                "heading": chunk.heading,
                "distance": round(distance, 3),
            })

        result =  {"answer": answer, "sources": sources}
    set_cached_answer(question, k , max_distance, document_id, result)
    return result