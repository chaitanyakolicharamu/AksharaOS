class Reranker:
    def rerank(
        self,
        query: str,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str],
        mode: str,
    ):
        ranked = []

        for rank, (doc, meta, chunk_id) in enumerate(
            zip(documents, metadatas, ids), start=1
        ):
            score = 0.0
            score += 1.0 / rank

            if query in doc:
                score += 0.50

            source_role = meta.get("source_role")

            if mode == "synonym" and source_role == "synonym_dictionary":
                score += 0.25

            if mode == "pure_telugu" and source_role == "pure_telugu_reference":
                score += 0.25

            if mode == "name":
                name_terms = [
                    "అమ్మాయి",
                    "బాలిక",
                    "యువతి",
                    "కన్య",
                    "చెలువ",
                    "సోయగి",
                    "ముద్దుగుమ్మ",
                    "చక్కనమ్మ",
                    "తామరకంటి",
                    "పువ్వుబోడి",
                ]

                if any(term in doc for term in name_terms):
                    score += 0.40

            quality_score = meta.get("quality_score") or 0
            score += float(quality_score) * 0.05

            ranked.append(
                {
                    "id": chunk_id,
                    "document": doc,
                    "metadata": meta,
                    "score": score,
                }
            )

        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked
