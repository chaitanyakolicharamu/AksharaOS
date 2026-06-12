from fastapi import FastAPI
from pydantic import BaseModel

from rag.retriever import Retriever

app = FastAPI(
    title="AksharaOS API",
    version="0.1.0",
)

retriever = Retriever()


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "AksharaOS",
    }


@app.post("/search")
def search(request: SearchRequest):
    results = retriever.retrieve(
        query=request.query,
        top_k=request.top_k,
    )

    return {
        "query": request.query,
        "mode": results["mode"],
        "results": [
            {
                "chunk_id": chunk_id,
                "metadata": metadata,
                "score": score,
                "text": document,
            }
            for chunk_id, metadata, score, document in zip(
                results["ids"][0],
                results["metadatas"][0],
                results["scores"][0],
                results["documents"][0],
            )
        ],
    }
