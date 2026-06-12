import chromadb
from sentence_transformers import SentenceTransformer

VECTOR_DB_DIR = "data/curated/vector_store"
COLLECTION_NAME = "bangaru_palukulu_knowledge"
EMBEDDING_MODEL = "BAAI/bge-m3"


class Retriever:
    def __init__(self):
        self.model = SentenceTransformer(EMBEDDING_MODEL)

        client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
        self.collection = client.get_collection(name=COLLECTION_NAME)

    def exact_search(self, query: str, top_k: int = 5):
        return self.collection.get(
            where_document={"$contains": query},
            limit=top_k,
        )

    def vector_search(self, query: str, top_k: int = 20):
        query_embedding = self.model.encode(
            [query],
            normalize_embeddings=True,
        ).tolist()

        return self.collection.query(
            query_embeddings=query_embedding,
            n_results=top_k,
        )

    def rerank(
        self,
        query: str,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str],
    ):
        ranked = []

        for rank, (doc, meta, chunk_id) in enumerate(
            zip(documents, metadatas, ids), start=1
        ):
            score = 0.0

            # Earlier vector rank is better
            score += 1.0 / rank

            # Strong boost when exact query appears in chunk
            if query in doc:
                score += 0.50

            # Synonym dictionary is usually better for word lookup
            if meta.get("source_role") == "synonym_dictionary":
                score += 0.15

            # OCR / text quality boost
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
        exact_results = self.exact_search(query, top_k=5)
        vector_results = self.vector_search(query, top_k=20)

        documents = []
        metadatas = []
        ids = []

        # Add exact matches first
        for i, doc in enumerate(exact_results.get("documents", [])):
            documents.append(doc)
            metadatas.append(exact_results["metadatas"][i])
            ids.append(exact_results["ids"][i])

        # Add vector matches
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
        )

        top_results = ranked[:top_k]

        return {
            "documents": [[item["document"] for item in top_results]],
            "metadatas": [[item["metadata"] for item in top_results]],
            "ids": [[item["id"] for item in top_results]],
            "scores": [[item["score"] for item in top_results]],
        }