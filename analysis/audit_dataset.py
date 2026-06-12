from pathlib import Path
import json
from collections import Counter
import re

CURATED_DIR = Path("data/curated")


def telugu_ratio(text):
    telugu_chars = re.findall(r"[\u0C00-\u0C7F]", text)
    useful_chars = re.findall(r"[\u0C00-\u0C7Fa-zA-Z0-9]", text)

    if not useful_chars:
        return 0

    return len(telugu_chars) / len(useful_chars)


def audit_dataset(dataset_path: Path):
    chunks = []

    with open(dataset_path, "r", encoding="utf-8") as file:
        for line in file:
            chunks.append(json.loads(line))

    if not chunks:
        return

    total_chunks = len(chunks)
    lengths = [len(chunk["text"]) for chunk in chunks]
    units = [chunk["unit_id"] for chunk in chunks]

    duplicate_counter = Counter(chunk["text"] for chunk in chunks)
    duplicates = [text for text, count in duplicate_counter.items() if count > 1]

    short_chunks = [chunk for chunk in chunks if len(chunk["text"]) < 100]
    long_chunks = [chunk for chunk in chunks if len(chunk["text"]) > 1000]
    ratios = [telugu_ratio(chunk["text"]) for chunk in chunks]

    document_id = chunks[0].get("document_id", dataset_path.parent.name)

    print("\n" + "=" * 80)
    print(f"DATASET AUDIT: {document_id}")
    print("=" * 80)

    print(f"File: {dataset_path}")
    print(f"Total chunks: {total_chunks}")
    print(f"Units/pages covered: {len(set(units))}")

    print("\nChunk Lengths")
    print(f"Minimum length: {min(lengths)}")
    print(f"Maximum length: {max(lengths)}")
    print(f"Average length: {sum(lengths) / total_chunks:.2f}")

    print("\nQuality")
    print(f"Average Telugu ratio: {sum(ratios) / total_chunks:.3f}")
    print(f"Short chunks (<100 chars): {len(short_chunks)}")
    print(f"Long chunks (>1000 chars): {len(long_chunks)}")
    print(f"Duplicate chunks: {len(duplicates)}")

    print("\nSample Short Chunks")
    for chunk in short_chunks[:3]:
        print(chunk["chunk_id"], "->", chunk["text"][:120])


def main():
    files = sorted(CURATED_DIR.glob("*/quality_chunks.jsonl"))

    if not files:
        print("No curated datasets found.")
        return

    for file_path in files:
        audit_dataset(file_path)


if __name__ == "__main__":
    main()
