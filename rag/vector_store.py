import chromadb


class VectorStore:
    def __init__(self, path: str, collection_name: str):
        self.client = chromadb.PersistentClient(path=path)
        self.collection = self.client.get_collection(name=collection_name)

    def exact_search(self, query: str, top_k: int = 5):
        return self.collection.get(
            where_document={"$contains": query},
            limit=top_k,
        )

    def vector_search(self, query_embeddings: list[list[float]], top_k: int = 20):
        return self.collection.query(
            query_embeddings=query_embeddings,
            n_results=top_k,
        )
