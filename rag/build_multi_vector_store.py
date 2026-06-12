from pathlib import Path
import json
import shutil

import chromadb
from sentence_transformers import SentenceTransformer

CURATED_DIR = Path("data/curated")
VECTOR_DB_DIR = "data/curated/vector_store"
COLLECTION_NAME = "bangaru_palukulu_knowledge"

EMBEDDING_MODEL = "BAAI/bge-m3"

SOURCE_ROLES = {
    "bangaru_nanelu": "pure_telugu_reference",
    "telugu_paryaya_nighantuvu": "synonym_dictionary",
}


def load_all_chunks():
    ids = []
    documents = []
    metadatas = []

    files = sorted(CURATED_DIR.glob("*/quality_chunks.jsonl"))

    for dataset_file in files:
        document_folder = dataset_file.parent.name
        source_role = SOURCE_ROLES.get(document_folder, "unknown")

        print(f"[LOAD] Reading: {dataset_file}")

        with open(dataset_file, "r", encoding="utf-8") as file:
            for line in file:
                chunk = json.loads(line)

                ids.append(chunk["chunk_id"])
                documents.append(chunk["text"])
                metadatas.append(
                    {
                        "document_id": chunk.get("document_id", document_folder),
                        "source_role": source_role,
                        "unit_type": chunk.get("unit_type", "unknown"),
                        "unit_id": chunk.get("unit_id", "unknown"),
                        "language": chunk.get("language", "te"),
                        "quality_score": chunk.get("quality_score", 0),
                    }
                )

    return ids, documents, metadatas


def main():
    print("[RESET] Removing old vector store...")
    shutil.rmtree(VECTOR_DB_DIR, ignore_errors=True)

    print("[LOAD] Loading embedding model...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    ids, documents, metadatas = load_all_chunks()

    print(f"[DATA] Total chunks loaded: {len(documents)}")

    if not documents:
        print("[STOP] No chunks found.")
        return

    print("[DB] Creating ChromaDB collection...")
    client = chromadb.PersistentClient(path=VECTOR_DB_DIR)

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Bangaru Palukulu multi-source Telugu knowledge base"},
    )

    print("[EMBED] Creating embeddings...")
    embeddings = model.encode(
        documents,
        batch_size=16,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    print("[DB] Saving vectors...")
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings.tolist(),
    )

    print("[DONE] Multi-source vector store created.")
    print(f"[PATH] {VECTOR_DB_DIR}")
    print(f"[COLLECTION] {COLLECTION_NAME}")


if __name__ == "__main__":
    main()
