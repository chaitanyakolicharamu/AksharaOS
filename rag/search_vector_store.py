import chromadb
from sentence_transformers import SentenceTransformer

VECTOR_DB_DIR = "data/curated/vector_store"
COLLECTION_NAME = "bangaru_nanelu"
EMBEDDING_MODEL = "BAAI/bge-m3"


def search(query: str, top_k: int = 5):
    model = SentenceTransformer(EMBEDDING_MODEL)
    client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
    collection = client.get_collection(name=COLLECTION_NAME)

    query_embedding = model.encode([query], normalize_embeddings=True).tolist()

    results = collection.query(query_embeddings=query_embedding, n_results=top_k)

    for i, document in enumerate(results["documents"][0], start=1):
        metadata = results["metadatas"][0][i - 1]
        distance = results["distances"][0][i - 1]

        print("\n" + "=" * 80)
        print(f"Rank: {i}")
        print(f"Distance: {distance}")
        print(f"Source: {metadata['document_id']} | {metadata['unit_id']}")
        print(document[:700])


if __name__ == "__main__":
    query = input("Enter Telugu search query: ")
    search(query)
