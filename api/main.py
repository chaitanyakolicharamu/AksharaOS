from functools import lru_cache
import os
from pathlib import Path
import re
import secrets
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from feedback.store import FeedbackStore
from knowledge.schema import normalize
from naming.catalog import Catalog, NameQuery
from rag.context_builder import ContextBuilder
from rag.context_compressor import ContextCompressor
from rag.generator import Generator
from rag.query_router import QueryRouter

app = FastAPI(title="AksharaOS API", version="0.2.0")


@lru_cache
def get_knowledge():
    from knowledge.search import KnowledgeSearch

    try:
        return KnowledgeSearch(
            Path(os.getenv("AKSHARA_KNOWLEDGE_DIR", "data/knowledge/index"))
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(
            503, "Knowledge index unavailable; run python -m knowledge.build"
        ) from exc


@lru_cache
def get_retriever():
    if os.getenv("AKSHARA_RETRIEVAL_BACKEND", "knowledge") == "legacy":
        from rag.retriever import Retriever

        return Retriever()
    return get_knowledge()


@lru_cache
def get_catalog():
    model = os.getenv("AKSHARA_RANKER")
    try:
        return Catalog(
            Path(os.getenv("AKSHARA_NAME_CATALOG", "data/names/reviewed.jsonl")),
            get_knowledge(),
            Path(model) if model else None,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(
            503, "Reviewed catalog or ranker is invalid; check server configuration"
        ) from exc


@lru_cache
def get_feedback():
    return FeedbackStore(
        Path(os.getenv("AKSHARA_FEEDBACK_DB", "data/private/feedback.sqlite3"))
    )


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def nonempty(cls, value):
        value = normalize(value)
        if not value:
            raise ValueError("query cannot be blank")
        return value


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    impression_id: str = Field(min_length=10, max_length=80)
    candidate_id: str = Field(min_length=10, max_length=80)
    vote: Literal["like", "dislike"]
    reason: Literal[
        "preference", "sound", "spelling", "too_common", "meaning_incorrect"
    ] = "preference"
    training_consent: bool = False


@app.get("/health")
def health():
    return {"status": "healthy", "service": "AksharaOS"}


@app.get("/ready")
def ready(knowledge=Depends(get_knowledge), catalog=Depends(get_catalog)):
    return {
        "knowledge_version": knowledge.version,
        "knowledge_records": len(knowledge.records),
        "catalog_version": catalog.version,
        "reviewed_names": len(catalog.names),
        "ranker_version": catalog.model_version,
        "public_launch_ready": False,
        "stage": "internal testing",
    }


@app.post("/search")
def search(body: SearchRequest, retriever=Depends(get_retriever)):
    results = retriever.retrieve(query=body.query, top_k=body.top_k)
    return {
        "query": body.query,
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


def name_response(body, request, response, catalog, store):
    rows = catalog.recommend(body)
    if not rows:
        return {
            "results": [],
            "impression_id": None,
            "status": "no_reviewed_matches",
            "message": "No reviewed names match yet. Dictionary words require name and meaning review.",
            "catalog_version": catalog.version,
            "knowledge_version": catalog.knowledge.version,
        }
    token = request.cookies.get("akshara_session") or secrets.token_urlsafe(32)
    if len(token) > 200:
        raise HTTPException(400, "Invalid session")
    try:
        impression = store.record_impression(token, body, rows, catalog)
    except ValueError as exc:
        raise HTTPException(429, str(exc)) from exc
    response.set_cookie(
        "akshara_session",
        token,
        httponly=True,
        samesite="strict",
        secure=os.getenv("AKSHARA_SECURE_COOKIES", "false").lower() == "true",
        max_age=30 * 86400,
    )
    return {
        "results": [
            {
                k: v
                for k, v in row.items()
                if k not in {"features", "reviewed_by", "reviewed_at"}
            }
            for row in rows
        ],
        "impression_id": impression,
        "catalog_version": catalog.version,
        "knowledge_version": catalog.knowledge.version,
        "ranker_version": catalog.model_version,
    }


@app.post("/names")
def names(
    body: NameQuery,
    request: Request,
    response: Response,
    catalog=Depends(get_catalog),
    store=Depends(get_feedback),
):
    return name_response(body, request, response, catalog, store)


@app.post("/feedback")
def feedback(body: FeedbackRequest, request: Request, store=Depends(get_feedback)):
    token = request.cookies.get("akshara_session")
    if not token:
        raise HTTPException(400, "First request a name suggestion in this session")
    try:
        vote_id = store.vote(
            token,
            body.impression_id,
            body.candidate_id,
            1 if body.vote == "like" else -1,
            body.reason,
            body.training_consent,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {
        "feedback_id": vote_id,
        "status": "pending_review",
        "training_consent": body.training_consent,
    }


@app.delete("/feedback")
def withdraw(request: Request, response: Response, store=Depends(get_feedback)):
    if token := request.cookies.get("akshara_session"):
        store.withdraw(token)
    response.delete_cookie("akshara_session")
    return {"status": "session_feedback_deleted"}


@app.post("/ask")
def ask(
    body: SearchRequest,
    request: Request,
    response: Response,
    retriever=Depends(get_retriever),
):
    if QueryRouter().detect_mode(body.query) == "name":
        query = body.query.casefold()
        girl = bool(
            re.search(r"\b(girl|female|ammayi|ammayila)\b|అమ్మాయి|బాలిక", query)
        )
        boy = bool(re.search(r"\b(boy|male|abbayi|abbayila)\b|అబ్బాయి|బాలుడు", query))
        name_query = NameQuery(
            query=body.query,
            gender="girl" if girl and not boy else "boy" if boy and not girl else None,
            pure_telugu=bool(re.search(r"అచ్చ|pure telugu|accha telugu", query)),
            top_k=body.top_k,
        )
        result = name_response(
            name_query, request, response, get_catalog(), get_feedback()
        )
        return {"query": body.query, "mode": "name", **result}
    results = retriever.retrieve(query=body.query, top_k=body.top_k)
    context = ContextBuilder().build(results)
    # The legacy compressor assumes comma-separated synonyms and drops multiword
    # dictionary definitions. Preserve attributed lexical passages in the new KB.
    structured = any(meta.get("evidence") for meta in results["metadatas"][0])
    compressed = (
        context[:4000]
        if structured
        else ContextCompressor().compress(query=body.query, context=context)
    )
    if not results["ids"][0]:
        answer = "The available sources do not contain enough information."
    elif results["mode"] == "synonym":
        answer = compressed
    else:
        try:
            answer = Generator().generate(query=body.query, context=compressed)
        except Exception as exc:
            raise HTTPException(
                503, "Local generation unavailable; use /search for source evidence"
            ) from exc
    return {
        "query": body.query,
        "mode": results["mode"],
        "answer": answer,
        "context_preview": compressed,
        "sources": [
            {"chunk_id": key, "metadata": meta, "score": score}
            for key, meta, score in zip(
                results["ids"][0], results["metadatas"][0], results["scores"][0]
            )
        ],
    }
