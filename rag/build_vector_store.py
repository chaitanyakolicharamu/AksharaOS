from pathlib import Path
import json

import chromadb
from sentence_transformers import SentenceTransformer

DATASET_PATH = Path("data/curated/bangaru_nanelu/quality_chunks.jsonl")
VECTOR_DB_DIR = "data/curated/vector_store"
COLLECTION_NAME = "bangaru_nanelu"

EMBEDDING_MODEL = "BAAI/bge-m3"


def main():
    print("[LOAD] Loading embedding model...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    print("[DB] Connecting to ChromaDB...")
    client = chromadb.PersistentClient(path=VECTOR_DB_DIR)

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Bangaru Nanelu Telugu knowledge chunks"},
    )

    ids = []
    documents = []
    metadatas = []

    with open(DATASET_PATH, "r", encoding="utf-8") as file:
        for line in file:
            chunk = json.loads(line)

            ids.append(chunk["chunk_id"])
            documents.append(chunk["text"])
            metadatas.append(
                {
                    "document_id": chunk["document_id"],
                    "unit_type": chunk["unit_type"],
                    "unit_id": chunk["unit_id"],
                    "language": chunk["language"],
                    "quality_score": chunk["quality_score"],
                }
            )

    print(f"[DATA] Loaded {len(documents)} chunks")

    print("[EMBED] Creating embeddings...")
    embeddings = model.encode(
        documents, batch_size=16, show_progress_bar=True, normalize_embeddings=True
    )

    print("[DB] Saving vectors to ChromaDB...")
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings.tolist(),
    )

    print("[DONE] Vector store created successfully.")
    print(f"[PATH] {VECTOR_DB_DIR}")


if __name__ == "__main__":
    main()
