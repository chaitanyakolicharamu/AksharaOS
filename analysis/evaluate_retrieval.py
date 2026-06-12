from rag.retriever import Retriever

TEST_QUERIES = [
    {"query": "పసికందు", "expected_terms": ["బిడ్డ", "శిశువు", "పసిపాప"]},
    {"query": "చిన్నవాడు", "expected_terms": ["పిన్నవాడు", "బాలుడు", "చిటికాడు"]},
    {"query": "కిరణము", "expected_terms": ["వెలుగు", "జ్యోతి", "ప్రభ"]},
    {"query": "ఆకాశము", "expected_terms": ["గగనము", "నింగి", "అంబరము"]},
    {
        "query": "అమ్మాయిల పేర్లు",
        "expected_terms": ["అమ్మాయి", "బాలిక", "యువతి", "కన్య"],
    },
    {"query": "బిడ్డ", "expected_terms": ["పసికందు", "శిశువు", "బాలకుడు"]},
    {"query": "బాలిక", "expected_terms": ["అమ్మాయి", "కన్య", "కుమారి"]},
    {"query": "యువతి", "expected_terms": ["తరుణి", "పడుచు", "జవ్వని"]},
    {"query": "వెలుగు", "expected_terms": ["జ్యోతి", "ప్రభ", "కాంతి"]},
    {"query": "చంద్రుడు", "expected_terms": ["నెల", "నిశాకర", "శశి"]},
    {"query": "పువ్వు", "expected_terms": ["పుష్పము", "సుమము", "విరి"]},
    {"query": "వాన", "expected_terms": ["వర్షము", "జలము", "మేఘము"]},
    {"query": "గాలి", "expected_terms": ["వాయువు", "పవనము", "మారుతము"]},
    {"query": "నీరు", "expected_terms": ["జలము", "తోయము", "వారి"]},
    {"query": "భూమి", "expected_terms": ["నేల", "ధరణి", "పృథివి"]},
    {"query": "అచ్చ తెలుగు", "expected_terms": ["అచ్చతెలుగు", "తెలుగు", "సాటి"]},
    {"query": "పేరు", "expected_terms": ["నామము", "పేరు"]},
    {"query": "కుక్క", "expected_terms": ["శునకము", "కుకురము", "నాయి"]},
    {"query": "పిల్లి", "expected_terms": ["మార్జాలము", "బిడాలము", "పిల్లి"]},
    {"query": "ఏనుగు", "expected_terms": ["గజము", "కరి", "కుంజరము"]},
]


def contains_expected(text: str, expected_terms: list[str]) -> bool:
    return any(term in text for term in expected_terms)


def first_relevant_rank(documents: list[str], expected_terms: list[str]) -> int | None:
    for rank, document in enumerate(documents, start=1):
        if contains_expected(document, expected_terms):
            return rank
    return None


def main():
    retriever = Retriever()

    total = len(TEST_QUERIES)
    hit_at_1 = 0
    hit_at_3 = 0
    hit_at_5 = 0
    reciprocal_rank_sum = 0.0

    print()
    print("=" * 100)
    print("RETRIEVAL EVALUATION V2")
    print("=" * 100)

    for item in TEST_QUERIES:
        query = item["query"]
        expected_terms = item["expected_terms"]

        results = retriever.retrieve(query=query, top_k=5)
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        ids = results["ids"][0]

        relevant_rank = first_relevant_rank(documents, expected_terms)

        if relevant_rank is not None:
            if relevant_rank <= 1:
                hit_at_1 += 1
            if relevant_rank <= 3:
                hit_at_3 += 1
            if relevant_rank <= 5:
                hit_at_5 += 1

            reciprocal_rank_sum += 1 / relevant_rank

        print()
        print("-" * 100)
        print(f"QUERY: {query}")
        print(f"EXPECTED: {expected_terms}")
        print(f"FIRST RELEVANT RANK: {relevant_rank if relevant_rank else 'NOT FOUND'}")
        print(f"HIT@1: {'PASS' if relevant_rank == 1 else 'FAIL'}")
        print(f"HIT@3: {'PASS' if relevant_rank and relevant_rank <= 3 else 'FAIL'}")
        print(f"HIT@5: {'PASS' if relevant_rank and relevant_rank <= 5 else 'FAIL'}")

        for rank, (doc, meta, chunk_id) in enumerate(
            zip(documents, metadatas, ids), start=1
        ):
            is_relevant = contains_expected(doc, expected_terms)

            print()
            print(f"Rank {rank} {'✅' if is_relevant else '❌'}")
            print(f"Chunk ID: {chunk_id}")
            print(f"Document: {meta.get('document_id')}")
            print(f"Source Role: {meta.get('source_role')}")
            print(f"Unit: {meta.get('unit_id')}")
            print(f"Preview: {doc[:250]}")

    mean_reciprocal_rank = reciprocal_rank_sum / total

    print()
    print("=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"Total Queries: {total}")
    print(f"Hit@1: {hit_at_1}/{total} ({hit_at_1 / total:.2%})")
    print(f"Hit@3: {hit_at_3}/{total} ({hit_at_3 / total:.2%})")
    print(f"Hit@5: {hit_at_5}/{total} ({hit_at_5 / total:.2%})")
    print(f"MRR: {mean_reciprocal_rank:.3f}")
    print("=" * 100)


if __name__ == "__main__":
    main()
