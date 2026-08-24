
from fastapi import  FastAPI, Depends, Body, HTTPException, status, Response , APIRouter,File, UploadFile

import hashlib
from typing import List

import fitz  # PyMuPDF
import tiktoken
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import select
from sqlalchemy.orm import Session
from config import settings
from google import genai
from google.genai import types
import models, oauth2
from database import SessionLocal, get_db
 # wherever your genai client lives
from conversations import fire_webhook

client = genai.Client(api_key=settings.api_key)

ROUTER = APIRouter(prefix="/documents", tags=["documents"])

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB, tune to your needs
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
}
EMBED_DIM = 768
EMBED_BATCH_SIZE = 100  # tune to API limits

# Chunk sizing is now in TOKENS, not words -- this is what the embedding
# model actually consumes, and word count is a loose (and misleading) proxy
# for it. gemini-embedding-001 doesn't ship its own public tokenizer, so we
# use tiktoken's cl100k_base as a close-enough stand-in for length
# estimation. It won't be byte-for-byte exact for a non-OpenAI model, but
# it's far more consistent than counting words.
CHUNK_SIZE_TOKENS = 400
CHUNK_OVERLAP_TOKENS = 60  # ~15% overlap so context isn't lost at boundaries

_tokenizer = tiktoken.get_encoding("cl100k_base")

_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    encoding_name="cl100k_base",
    chunk_size=CHUNK_SIZE_TOKENS,
    chunk_overlap=CHUNK_OVERLAP_TOKENS,
    # Tries these separators in order: paragraph breaks first, then lines,
    # then sentences, then words, then characters as a last resort. This is
    # the actual fix over the old approach -- it only falls back to a raw
    # character cut if it truly can't find a cleaner boundary.
    separators=["\n\n", "\n", ". ", " ", ""],
)


def extract_text(content: bytes, content_type: str) -> str:
    if content_type == "application/pdf":
        with fitz.open(stream=content, filetype="pdf") as pdf:
            return "".join(page.get_text() for page in pdf)
    return content.decode("utf-8", errors="replace")


def chunk_text(text: str) -> List[str]:
    """Token-aware, structure-respecting chunking.

    Splits on paragraph breaks first, falling back to lines, sentences,
    words, and finally raw characters only if nothing cleaner is found.
    Chunk size + overlap are measured in tokens (via tiktoken) rather than
    words, so chunks are sized against what the embedding model actually
    sees instead of a loose word-count proxy.
    """

    if not text.strip():
        return []
    return [c for c in _splitter.split_text(text) if c.strip()]


def embed_documents(texts: List[str]) -> List[list]:
    """Batched embedding calls, chunked to EMBED_BATCH_SIZE."""
    vectors = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i:i + EMBED_BATCH_SIZE]
        result = client.models.embed_content(
            model="gemini-embedding-001",
            contents=batch,
            config=types.EmbedContentConfig(
                output_dimensionality=EMBED_DIM,
                task_type="RETRIEVAL_DOCUMENT",  # now actually applied
            ),
        )
        vectors.extend(e.values for e in result.embeddings)
    return vectors

# vectors = []
# for e in result.embeddings:
#     vectors.append(e.values)


def run_document_webhook(document_id: int, filename: str, chunk_count: int, user_id: int):
    """Background task opens its OWN session -- never reuse the request's
    db session here, it may already be closed/returned to the pool by the
    time this runs."""
    db = SessionLocal()
    try:
        fire_webhook(
            event_type="document_uploaded",
            payload={
                "document_id": document_id,
                "filename": filename,
                "chunk_count": chunk_count,
            },
            db=db,
            user_id=user_id,
        )
    finally:
        db.close()


@ROUTER.post("/")
async def post_docs(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="only admins can upload documents")

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"unsupported content type: {file.content_type}. "
                   f"allowed: {sorted(ALLOWED_CONTENT_TYPES)}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="file too large")

    content_hash = hashlib.sha256(content).hexdigest()
    existing = db.execute(
        select(models.Document).where(models.Document.content_hash == content_hash)
    ).scalar_one_or_none()
    if existing:
        # Idempotent re-upload: same bytes already indexed, don't re-embed.
        return {
            "text": "document already indexed, skipping re-embedding",
            "doc_id": existing.id,
        }

    try:
        text = extract_text(content, file.content_type)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"could not extract text: {e}")

    if not text.strip():
        raise HTTPException(
            status_code=422,
            detail="no extractable text found (scanned/image-only PDF?)",
        )

    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(status_code=422, detail="no chunks produced from document text")

    # Do the (slow, external, failure-prone) embedding call BEFORE touching
    # the DB at all -- if it fails, we haven't written anything, no cleanup
    # or rollback needed.
    try:
        vectors = embed_documents(chunks)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"embedding provider error: {e}")

    if len(vectors) != len(chunks):
        raise HTTPException(status_code=502, detail="embedding count mismatch")

    # Now do all DB writes in one transaction: Document + every Chunk,
    # committed together. Any failure here rolls back everything, so we
    # never end up with an orphaned Document that has zero/partial chunks.
    try:
        doc = models.Document(
            user_id=current_user.id,
            filename=file.filename,
            content_hash=content_hash,
        )
        db.add(doc)
        db.flush()  # get doc.id without committing yet

        for chunk_str, vector in zip(chunks, vectors):
            db.add(models.Chunk(document_id=doc.id, text=chunk_str, embedding=vector))

        db.commit()
        db.refresh(doc)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="failed to save document and chunks")

    background_tasks.add_task(
        run_document_webhook,
        document_id=doc.id,
        filename=file.filename,
        chunk_count=len(chunks),
        user_id=current_user.id,
    )

    return {"text": "doc uploaded successfully", "doc_id": doc.id}

@ROUTER.get('/')
async def get_docs(db: Session = Depends(get_db),current_user : int = Depends(oauth2.get_current_user)):
    query = db.execute(select(models.Document)
             .order_by( models.Document.user_id == current_user
        ,models.Document.created_at)
                       ).scalars().all()

    return query


@ROUTER.delete('/{id}')
async def delete_docs(id: int,db: Session = Depends(get_db),current_user : int = Depends(oauth2.get_current_user)):
    user_is_admin = db.execute(select(models.User)
                      .where(models.User.id == current_user.id)).scalar_one_or_none()
    if not user_is_admin:
        raise HTTPException(status_code=404, detail="user not found")
    if not user_is_admin.is_admin:
        raise HTTPException(status_code=404, detail="only admins can upload documents")

    doc = db.execute(select(models.Document).where(models.Document.id == id)).scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user negative")
    db.delete(doc)
    db.commit()
    return {"message": "document deleted"}





# text = "the cat sat on the mat and looked around"

# words = text.split()
# ["the", "cat", "sat", "on", "the", "mat", "and", "looked", "around"]

# chunks = [" ".join(words[i:i+4]) for i in range(0, len(words), 4)]


# chunk 1: words[0:4]  → ["the", "cat", "sat", "on"]    → "the cat sat on"
# chunk 2: words[4:8]  → ["the", "mat", "and", "looked"] → "the mat and looked"
# chunk 3: words[8:12] → ["around"]                       → "around"

# print(chunks)
# ["the cat sat on", "the mat and looked", "around"]