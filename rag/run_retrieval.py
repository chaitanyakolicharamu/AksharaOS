from knowledge.unified_search import UnifiedSearch
from rag.context_builder import ContextBuilder


def main():
    query = input("Question: ")

    retriever = UnifiedSearch()
    results = retriever.retrieve(query=query, top_k=5)

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    ids = results["ids"][0]

    print("\n")
    print("=" * 100)
    print("RETRIEVAL RESULTS")
    print("=" * 100)

    for i, (doc, meta, chunk_id) in enumerate(zip(documents, metadatas, ids), start=1):
        print("\n" + "-" * 100)
        print(f"Rank: {i}")
        print(f"Chunk ID: {chunk_id}")
        print(f"Knowledge version: {meta.get('knowledge_version')}")
        print(f"Review status: {meta.get('review_status')} / {meta.get('text_status')}")
        for evidence in meta.get("evidence", []):
            print(
                f"Source: {evidence.get('source_title')} | PDF page: {evidence.get('pdf_page')} | {evidence.get('url') or evidence.get('locator')}"
            )
        print("-" * 100)
        print(doc[:1000])

    builder = ContextBuilder()
    context = builder.build(results)

    print("\n")
    print("=" * 100)
    print("FINAL CONTEXT SENT TO GENERATOR")
    print("=" * 100)
    print(context)


if __name__ == "__main__":
    main()
