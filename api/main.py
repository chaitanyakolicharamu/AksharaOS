from fastapi import FastAPI
from pydantic import BaseModel

from rag.context_builder import ContextBuilder
from rag.context_compressor import ContextCompressor
from rag.generator import Generator
from rag.retriever import Retriever

app = FastAPI(
    title="AksharaOS API",
    version="0.1.0",
)

retriever = Retriever()
context_builder = ContextBuilder()
compressor = ContextCompressor()
generator = Generator()


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class AskRequest(BaseModel):
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
                "preview": document[:500],
            }
            for chunk_id, metadata, score, document in zip(
                results["ids"][0],
                results["metadatas"][0],
                results["scores"][0],
                results["documents"][0],
            )
        ],
    }


@app.post("/ask")
def ask(request: AskRequest):
    results = retriever.retrieve(
        query=request.query,
        top_k=request.top_k,
    )

    context = context_builder.build(results)

    compressed_context = compressor.compress(
        query=request.query,
        context=context,
    )

    if results["mode"] == "synonym":
        answer = compressed_context
    else:
        answer = generator.generate(
            query=request.query,
            context=compressed_context,
        )

    return {
        "query": request.query,
        "mode": results["mode"],
        "answer": answer,
        "context_preview": compressed_context,
        "sources": [
            {
                "chunk_id": chunk_id,
                "metadata": metadata,
                "score": score,
            }
            for chunk_id, metadata, score in zip(
                results["ids"][0],
                results["metadatas"][0],
                results["scores"][0],
            )
        ],
    }
