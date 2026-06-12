class RetrievalEvaluator:
    def __init__(self, retriever, test_queries: list[dict]):
        self.retriever = retriever
        self.test_queries = test_queries

    def contains_expected(self, text: str, expected_terms: list[str]) -> bool:
        return any(term in text for term in expected_terms)

    def first_relevant_rank(
        self, documents: list[str], expected_terms: list[str]
    ) -> int | None:
        for rank, document in enumerate(documents, start=1):
            if self.contains_expected(document, expected_terms):
                return rank
        return None

    def evaluate(self, top_k: int = 5):
        total = len(self.test_queries)

        hit_at_1 = 0
        hit_at_3 = 0
        hit_at_5 = 0
        reciprocal_rank_sum = 0.0

        detailed_results = []

        for item in self.test_queries:
            query = item["query"]
            expected_terms = item["expected_terms"]

            results = self.retriever.retrieve(query=query, top_k=top_k)
            documents = results["documents"][0]
            metadatas = results["metadatas"][0]
            ids = results["ids"][0]

            relevant_rank = self.first_relevant_rank(documents, expected_terms)

            if relevant_rank is not None:
                if relevant_rank <= 1:
                    hit_at_1 += 1
                if relevant_rank <= 3:
                    hit_at_3 += 1
                if relevant_rank <= 5:
                    hit_at_5 += 1

                reciprocal_rank_sum += 1 / relevant_rank

            detailed_results.append(
                {
                    "query": query,
                    "expected_terms": expected_terms,
                    "first_relevant_rank": relevant_rank,
                    "results": [
                        {
                            "rank": rank,
                            "chunk_id": chunk_id,
                            "document_id": meta.get("document_id"),
                            "source_role": meta.get("source_role"),
                            "unit_id": meta.get("unit_id"),
                            "is_relevant": self.contains_expected(doc, expected_terms),
                            "preview": doc[:250],
                        }
                        for rank, (doc, meta, chunk_id) in enumerate(
                            zip(documents, metadatas, ids), start=1
                        )
                    ],
                }
            )

        summary = {
            "total_queries": total,
            "hit_at_1": hit_at_1,
            "hit_at_3": hit_at_3,
            "hit_at_5": hit_at_5,
            "hit_at_1_percent": hit_at_1 / total,
            "hit_at_3_percent": hit_at_3 / total,
            "hit_at_5_percent": hit_at_5 / total,
            "mrr": reciprocal_rank_sum / total,
        }

        return {
            "summary": summary,
            "details": detailed_results,
        }
