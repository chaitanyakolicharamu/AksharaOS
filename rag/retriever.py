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

    def exact_search(self, query: str, top_k: int = 3):
        """
        Exact keyword search.
        Useful for dictionary words like:
        పసికందు, చిన్నవాడు, కిరణము
        """
        results = self.collection.get(where_document={"$contains": query}, limit=top_k)

        return results

    def vector_search(self, query: str, top_k: int = 5):
        """
        Semantic vector search using BGE-M3.
        Useful for concept queries.
        """
        query_embedding = self.model.encode([query], normalize_embeddings=True).tolist()

        results = self.collection.query(
            query_embeddings=query_embedding, n_results=top_k
        )

        return results

    def retrieve(self, query: str, top_k: int = 5):
        exact_results = self.exact_search(query, top_k=3)
        vector_results = self.vector_search(query, top_k=top_k)

        documents = []
        metadatas = []
        ids = []

        # Add exact matches first
        for i, doc in enumerate(exact_results.get("documents", [])):
            documents.append(doc)
            metadatas.append(exact_results["metadatas"][i])
            ids.append(exact_results["ids"][i])

        # Add vector matches, avoid duplicates
        vector_docs = vector_results["documents"][0]
        vector_metas = vector_results["metadatas"][0]
        vector_ids = vector_results["ids"][0]

        for doc, meta, chunk_id in zip(vector_docs, vector_metas, vector_ids):
            if chunk_id not in ids:
                documents.append(doc)
                metadatas.append(meta)
                ids.append(chunk_id)

        return {
            "documents": [documents[:top_k]],
            "metadatas": [metadatas[:top_k]],
            "ids": [ids[:top_k]],
        }
