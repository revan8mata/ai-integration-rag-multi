from sqlalchemy.orm import Session
from sqlalchemy import select
import models
from config import settings
from google import genai
from google.genai import types

client = genai.Client(api_key=settings.api_key)

async def get_relevant_chunks(query: str,user_id: int, db: Session) -> str:
    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents=query,
        config=types.EmbedContentConfig(output_dimensionality=768,
                                        task_type="RETRIEVAL_QUERY")
    )
    query_vector = result.embeddings[0].values

    results = db.execute(
        select(models.Chunk)
        .join(models.Document)
        # .where(models.Document.user_id == user_id)
        .order_by(models.Chunk.embedding.cosine_distance(query_vector))
        .limit(5)
    ).scalars().all()
    print(results)
    return "\n\n".join([chunk.text for chunk in results])

# vector comperasion point


    # 1. embed the query
    # 2. find similar chunks
    # 3. return them as a single string to inject into the prompt