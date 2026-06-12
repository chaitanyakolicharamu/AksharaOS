from rag.evaluator import RetrievalEvaluator
from rag.retriever import Retriever

TEST_QUERIES = [
    {"query": "పసికందు", "expected_terms": ["బిడ్డ", "శిశువు", "పసిపాప"]},
    {
        "query": "చిన్నవాడు",
        "expected_terms": ["పిన్నవాడు", "బాలుడు", "చిటికాడు"],
    },
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


def print_results(evaluation: dict):
    print()
    print("=" * 100)
    print("RETRIEVAL EVALUATION")
    print("=" * 100)

    for item in evaluation["details"]:
        print()
        print("-" * 100)
        print(f"QUERY: {item['query']}")
        print(f"EXPECTED: {item['expected_terms']}")
        print(
            "FIRST RELEVANT RANK: "
            f"{item['first_relevant_rank'] if item['first_relevant_rank'] else 'NOT FOUND'}"
        )

        for result in item["results"]:
            print()
            print(f"Rank {result['rank']} {'✅' if result['is_relevant'] else '❌'}")
            print(f"Chunk ID: {result['chunk_id']}")
            print(f"Document: {result['document_id']}")
            print(f"Source Role: {result['source_role']}")
            print(f"Unit: {result['unit_id']}")
            print(f"Preview: {result['preview']}")

    summary = evaluation["summary"]

    print()
    print("=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"Total Queries: {summary['total_queries']}")
    print(
        f"Hit@1: {summary['hit_at_1']}/{summary['total_queries']} "
        f"({summary['hit_at_1_percent']:.2%})"
    )
    print(
        f"Hit@3: {summary['hit_at_3']}/{summary['total_queries']} "
        f"({summary['hit_at_3_percent']:.2%})"
    )
    print(
        f"Hit@5: {summary['hit_at_5']}/{summary['total_queries']} "
        f"({summary['hit_at_5_percent']:.2%})"
    )
    print(f"MRR: {summary['mrr']:.3f}")
    print("=" * 100)


def main():
    retriever = Retriever()
    evaluator = RetrievalEvaluator(
        retriever=retriever,
        test_queries=TEST_QUERIES,
    )

    evaluation = evaluator.evaluate(top_k=5)
    print_results(evaluation)


if __name__ == "__main__":
    main()
