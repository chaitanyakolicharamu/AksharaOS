from sentence_transformers import SentenceTransformer

from rag.vector_store import VectorStore

VECTOR_DB_DIR = "data/curated/vector_store"
COLLECTION_NAME = "bangaru_palukulu_knowledge"
EMBEDDING_MODEL = "BAAI/bge-m3"


class Retriever:
    def __init__(self):
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        self.vector_store = VectorStore(
            path=VECTOR_DB_DIR,
            collection_name=COLLECTION_NAME,
        )

    def detect_mode(self, query: str) -> str:
        pure_telugu_terms = ["అచ్చ", "అచ్చతెలుగు", "తెలుగు మాట", "సాటి మాట"]
        name_terms = ["పేర్లు", "పేరు", "అమ్మాయిల", "అబ్బాయిల"]

        if any(term in query for term in pure_telugu_terms):
            return "pure_telugu"

        if any(term in query for term in name_terms):
            return "name"

        return "synonym"

    def exact_search(self, query: str, top_k: int = 5):
        return self.vector_store.exact_search(query=query, top_k=top_k)

    def vector_search(self, query: str, top_k: int = 20):
        query_embedding = self.model.encode(
            [query],
            normalize_embeddings=True,
        ).tolist()

        return self.vector_store.vector_search(
            query_embeddings=query_embedding,
            top_k=top_k,
        )

    def rerank(
        self,
        query: str,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str],
        mode: str,
    ):
        ranked = []

        for rank, (doc, meta, chunk_id) in enumerate(
            zip(documents, metadatas, ids), start=1
        ):
            score = 0.0
            score += 1.0 / rank

            if query in doc:
                score += 0.50

            source_role = meta.get("source_role")

            if mode == "synonym" and source_role == "synonym_dictionary":
                score += 0.25

            if mode == "pure_telugu" and source_role == "pure_telugu_reference":
                score += 0.25

            if mode == "name":
                name_terms = [
                    "అమ్మాయి",
                    "బాలిక",
                    "యువతి",
                    "కన్య",
                    "చెలువ",
                    "సోయగి",
                    "ముద్దుగుమ్మ",
                    "చక్కనమ్మ",
                    "తామరకంటి",
                    "పువ్వుబోడి",
                ]

                if any(term in doc for term in name_terms):
                    score += 0.40

            quality_score = meta.get("quality_score") or 0
            score += float(quality_score) * 0.05

            ranked.append(
                {
                    "id": chunk_id,
                    "document": doc,
                    "metadata": meta,
                    "score": score,
                }
            )

        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked

    def retrieve(self, query: str, top_k: int = 5):
        mode = self.detect_mode(query)

        exact_results = self.exact_search(query, top_k=5)
        vector_results = self.vector_search(query, top_k=20)

        documents = []
        metadatas = []
        ids = []

        for i, doc in enumerate(exact_results.get("documents", [])):
            documents.append(doc)
            metadatas.append(exact_results["metadatas"][i])
            ids.append(exact_results["ids"][i])

        vector_docs = vector_results["documents"][0]
        vector_metas = vector_results["metadatas"][0]
        vector_ids = vector_results["ids"][0]

        for doc, meta, chunk_id in zip(vector_docs, vector_metas, vector_ids):
            if chunk_id not in ids:
                documents.append(doc)
                metadatas.append(meta)
                ids.append(chunk_id)

        ranked = self.rerank(
            query=query,
            documents=documents,
            metadatas=metadatas,
            ids=ids,
            mode=mode,
        )

        top_results = ranked[:top_k]

        return {
            "mode": mode,
            "documents": [[item["document"] for item in top_results]],
            "metadatas": [[item["metadata"] for item in top_results]],
            "ids": [[item["id"] for item in top_results]],
            "scores": [[item["score"] for item in top_results]],
        }
