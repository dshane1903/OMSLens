from fastapi import FastAPI

from shared.schemas.models import EmbeddingRequest, EmbeddingResponse
from shared.utils.ai import embed_texts
from shared.utils.observability import instrument_fastapi_app

app = FastAPI(title="RAG Embedding Service", version="0.1.0")
instrument_fastapi_app(app, "embedding-service")


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "service": "embedding-service"}


@app.post("/embed", response_model=EmbeddingResponse)
async def embed_text(request: EmbeddingRequest) -> EmbeddingResponse:
    return EmbeddingResponse(vectors=await embed_texts(request.texts))
