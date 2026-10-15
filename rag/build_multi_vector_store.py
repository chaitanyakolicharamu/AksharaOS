"""Build a combined Chroma index in a NEW directory, preserving the active index."""

import argparse
import json
from pathlib import Path
import re

from ingestion.config import load_config

CURATED_DIR = Path("data/curated")
VECTOR_DB_DIR = "data/curated/vector_store_next"
COLLECTION_NAME = "bangaru_palukulu_knowledge"
EMBEDDING_MODEL = "BAAI/bge-m3"


def load_all_chunks(curated_dir=CURATED_DIR, knowledge_index=None):
    roles = {key: config.source_role for key, config in load_config().documents.items()}
    files = sorted(Path(curated_dir).glob("*/quality_chunks.jsonl"))
    if knowledge_index:
        root = Path(knowledge_index)
        version = (root / "CURRENT").read_text(encoding="utf-8").strip()
        if not re.fullmatch(r"[a-f0-9]{20}", version):
            raise ValueError("Invalid knowledge version")
        files.append(root / "versions" / version / "quality_chunks.jsonl")
    ids, documents, metadatas, seen = [], [], [], set()
    for dataset_file in files:
        folder = dataset_file.parent.name
        for line in dataset_file.read_text(encoding="utf-8").splitlines():
            chunk = json.loads(line)
            key = chunk["chunk_id"]
            if key in seen:
                continue
            seen.add(key)
            ids.append(key)
            documents.append(chunk["text"])
            metadata = {
                "document_id": chunk.get("document_id", folder),
                "source_role": chunk.get("source_role", roles.get(folder, "unknown")),
                "unit_type": chunk.get("unit_type", "unknown"),
                "unit_id": chunk.get("unit_id", "unknown"),
                "language": chunk.get("language", "te"),
                "quality_score": chunk.get("quality_score", 0) or 0,
            }
            if chunk.get("evidence"):
                # Chroma metadata values must be scalar. Keep all citations in JSON.
                metadata["evidence_json"] = json.dumps(
                    chunk["evidence"], ensure_ascii=False
                )
            metadatas.append(metadata)
    return ids, documents, metadatas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(VECTOR_DB_DIR))
    parser.add_argument("--knowledge-index", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(
            "Output already exists. Choose a new directory; the active store is never deleted."
        )
    ids, documents, metadatas = load_all_chunks(knowledge_index=args.knowledge_index)
    if not documents:
        parser.error("No chunks found")
    import chromadb
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMBEDDING_MODEL)
    client = chromadb.PersistentClient(path=str(args.output))
    collection = client.get_or_create_collection(name=COLLECTION_NAME)
    for offset in range(0, len(ids), 128):
        texts = documents[offset : offset + 128]
        embeddings = model.encode(texts, batch_size=16, normalize_embeddings=True)
        collection.add(
            ids=ids[offset : offset + 128],
            documents=texts,
            metadatas=metadatas[offset : offset + 128],
            embeddings=embeddings.tolist(),
        )
    print(
        json.dumps(
            {
                "chunks": collection.count(),
                "output": str(args.output),
                "activation": "Set AKSHARA_VECTOR_DB to this path after evaluating the new index.",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
