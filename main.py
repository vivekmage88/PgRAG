from fastapi import FastAPI, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from database import get_db
from models import Document
from schemas import AskRequest, AskResponse, DocumentOut
from answer import answer_question
import os
import re
from fastapi import File, UploadFile, Form, HTTPException
from ingest import build_chunks, extract_pages
from embed import embed_in_batches
from store import save_document

app = FastAPI(title="Document RAG API", version="1.0.0")

UPLOAD_DIR = "uploads"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
PDF_MAGIC = b"%PDF"



@app.get("/health")
def health():
    return {"status": "ok"}

def safe_filename(name: str) -> str:
    base = os.path.basename(name)
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    return cleaned[:100]


@app.get("/documents", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)):
    stmt = select(Document).order_by(Document.created_at.desc())
    return db.scalars(stmt).all()

@app.post("/documents", status_code=201, response_model=DocumentOut)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    db: Session = Depends(get_db),
):
    contents = await file.read()

    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds 20 MB")

    if not contents.startswith(PDF_MAGIC):
        raise HTTPException(status_code=400, detail="Not a PDF file")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    path = os.path.join(UPLOAD_DIR, safe_filename(file.filename))

    with open(path, "wb") as f:
        f.write(contents)

    chunks = build_chunks(path)
    if not chunks:
        raise HTTPException(status_code=400, detail="No extractable text found")

    texts = []
    for chunk in chunks:
        texts.append(chunk["content"])

    vectors = embed_in_batches(texts)
    page_count = len(extract_pages(path))

    return save_document(db, title, safe_filename(file.filename), page_count, chunks, vectors)


@app.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest, db: Session = Depends(get_db)):
    if payload.document_id is not None:
        document = db.get(Document, payload.document_id)
        if document is None:
            raise HTTPException(
                status_code=404,
                detail=f"No document with id {payload.document_id}",
            )

    return answer_question(
        db,
        question=payload.question,
        k=payload.k,
        max_distance=payload.max_distance,
        document_id=payload.document_id,
    )
    
@app.delete("/documents/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)

    if document is None:
        raise HTTPException(status_code=404, detail=f"No document with id {document_id}")

    title = document.title
    db.delete(document)
    db.commit()

    return {"deleted": document_id, "title": title}