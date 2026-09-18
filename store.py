from sqlalchemy.orm import Session
from models import Chunk, Document

def save_document(db: Session, title: str, filename: str, page_count: int, chunks: list[dict], vectors: list[list[float]]):
    if len(chunks) != len(vectors):
        raise ValueError(f"{len(chunks)} chunks but {len(vectors)} vectors")
    
    document = Document(title = title, filename = filename, page_count = page_count)
    db.add(document)
    db.flush()
    
    
    for i in range(len(chunks)):
        chunk = chunks[i]
        row = Chunk(
            document_id = document.id,
            page = chunk["page"],
            heading = chunk["heading"],
            content = chunk["content"],
            token_count = chunk["token_count"],
            embedding = vectors[i],
        )
        db.add(row)
    db.commit()
    db.refresh(document)
    return document


if __name__ == "__main__":
    from database import SessionLocal
    from ingest import build_chunks
    from embed import embed_in_batches

    chunks = build_chunks("fastapi.pdf")

    texts = []
    for chunk in chunks:
        texts.append(chunk["content"])

    vectors = embed_in_batches(texts)

    db = SessionLocal()
    try:
        doc = save_document(db, "FastAPI Reference", "fastapi.pdf", 30, chunks, vectors)
        print(f"document id {doc.id}, {len(chunks)} chunks stored")
    finally:
        db.close()