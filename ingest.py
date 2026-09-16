from pypdf import PdfReader
import re
import tiktoken
from pprint import pprint

ENCODER = tiktoken.get_encoding("cl100k_base")

def count_tokens(text:str) -> int:
    return len(ENCODER.encode(text))

BOILERPLATE = [
    re.compile(r"^FastAPI RAG Reference \| \d+/\d+$", re.M),
    re.compile(r"^FASTAPI-RAG-\d+ \| Page \d+ of \d+$", re.M),
    re.compile(r"^PAGE-ID: [A-Z0-9\-]+$", re.M),
    re.compile(r"^Original reference-style content.*$", re.M),
    re.compile(r"^Synthetic FastAPI learning material.*$", re.M),
]


# function for extarcting pdf in to text
def extract_pages(path: str) -> list[tuple[int, str]]:
    reader = PdfReader(path)
    pages = []
    
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append((page_number,text))
        else:
            print(f"Page {page_number}: Text not found, Skipped")
    return pages

def clean_text(text: str) -> str:
    for pattern in BOILERPLATE:
        text = pattern.sub("", text)

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()

def split_heading_and_body(text: str) -> tuple[str, str]:
    part = text.split("\n", 1)
    heading = part[0].strip()
    
    if len(part) > 1:
        body = part[1].strip()
    else:
        body = ""
    return heading, body
    
    
def split_into_chunks(text: str, max_tokens: int=300, overlap_tokens: int = 50) -> list[str]:
    token_ids = ENCODER.encode(text)
    
    if len(token_ids) <= max_tokens:
        return [text]
    
    chunks = []
    start = 0
    while start < len(token_ids):
        end = start + max_tokens
        window = token_ids[start : end]
        chunks.append(ENCODER.decode(window))
        
        if end >= len(token_ids):
            break
        
        start = end - overlap_tokens
    return chunks



def build_chunks(path:str) -> list[dict]:
    pages = extract_pages(path)
    result = []
    
    for page_number, raw in pages:
        cleaned = clean_text(raw)
        heading, body = split_heading_and_body(cleaned)
        
        pieces = split_into_chunks(body, max_tokens=300, overlap_tokens=50)
        
        for piece in pieces:
            content = f"{heading}\n\n{piece}"
            result.append({
                "page": page_number,
                "heading": heading,
                "content": content,
                "token_count": count_tokens(content),
            })
    return result
        





if __name__ == '__main__':
    chunks = build_chunks("fastapi.pdf")
    print(f"{len(chunks)} chunks")

    sizes = []
    for chunk in chunks:
        sizes.append(chunk["token_count"])
    print(f"tokens: min {min(sizes)}, max {max(sizes)}, avg {sum(sizes) // len(sizes)}")

    print(f"\n{chunks[0]['page']} | {chunks[0]['heading']}")
    print(chunks[0]["content"][:200])