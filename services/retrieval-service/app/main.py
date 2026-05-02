import httpx
from fastapi import FastAPI, HTTPException

from shared.schemas.models import QueryRequest, QueryResponse, RetrievedChunk
from shared.utils.cache import get_cached_json, set_cached_json
from shared.utils.config import get_settings
from shared.utils.db import db_connection, ensure_schema, serialize_vector
from shared.utils.service_client import post_json

app = FastAPI(title="RAG Retrieval Service", version="0.1.0")
settings = get_settings()


@app.on_event("startup")
def startup() -> None:
    ensure_schema()


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "service": "retrieval-service"}


@app.post("/retrieve", response_model=QueryResponse)
async def retrieve_context(request: QueryRequest) -> QueryResponse:
    cache_key = f"query:{request.question}:{request.top_k}"
    cached = get_cached_json(cache_key)
    if cached:
        return QueryResponse.model_validate(cached)

    try:
        embedding_payload = await post_json(
            f"{settings.embedding_service_url}/embed",
            {"texts": [request.question]},
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    query_vector = embedding_payload["vectors"][0]

    with db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    document_id,
                    chunk_index,
                    text,
                    1 - (embedding <=> %s::vector) AS score
                FROM chunks
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (
                    serialize_vector(query_vector),
                    serialize_vector(query_vector),
                    request.top_k,
                ),
            )
            rows = list(cursor.fetchall())

    chunks = [
        RetrievedChunk(
            document_id=row["document_id"],
            chunk_index=row["chunk_index"],
            score=float(row["score"]),
            text=row["text"],
        )
        for row in rows
    ]

    try:
        answer_payload = await post_json(
            f"{settings.llm_service_url}/generate",
            {
                "question": request.question,
                "context": [chunk.text for chunk in chunks],
            },
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    response = QueryResponse(
        answer=answer_payload["answer"],
        chunks=chunks,
    )
    set_cached_json(cache_key, response.model_dump())
    return response
