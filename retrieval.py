from sqlalchemy import Select
from sqlalchemy.orm import Session
from models import Chunk
from embed import embed_texts



def search(db: Session, question: str, k: int = 5, max_distance: float = 1.2, document_id: int | None = None):
    question_vector = embed_texts([question])[0]
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


if __name__ == '__main__':
    from database import SessionLocal
    db = SessionLocal()
    
    for question in ["what is FastAPI", "what is capital of France"]:
        print(f"\n{question}")
        for chunk, distance in search(db, question, max_distance=0.6):
            print(f"  {round(distance, 3)}  p{chunk.page}  {chunk.heading}")
    
    
    
    