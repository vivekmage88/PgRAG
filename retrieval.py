from sqlalchemy import Select
from sqlalchemy.orm import Session
from models import Chunk
from embed import embed_texts
from cache import get_cached_embedding, set_cached_embedding



def search(db: Session, question: str, k: int = 5, max_distance: float = 1.2, document_id: int | None = None):
    question_vector = get_query_vector(question)
    distance = Chunk.embedding.cosine_distance(question_vector)
    stmt = Select(Chunk, distance.label("distance"))    
    
    
    if document_id is not None:
        stmt = stmt.where(Chunk.document_id == document_id)
        
    stmt = stmt.order_by(distance).limit(k)
    rows = db.execute(stmt).all()
    
    matches = []
    
    for chunk, dist in rows:
        if dist <= max_distance:
            matches.append((chunk, dist))
    
    return matches

def get_query_vector(question: str):
    cached = get_cached_embedding(question)
    if cached is not None:
        return cached
    vector = embed_texts([question])[0]
    set_cached_embedding(question, vector)
    return vector
    
    
    
    