class ContextBuilder:
    def build(self, retrieval_results, max_chars=6000):
        documents = retrieval_results["documents"][0]
        metadata = retrieval_results.get("metadatas", [[]])[0]
        if not documents:
            return ""
        # Budget every selected passage so the cited source list matches context.
        per_document = (max_chars - 2 * (len(documents) - 1)) // len(documents)
        parts = []
        for number, document in enumerate(documents, 1):
            meta = metadata[number - 1] if len(metadata) >= number else {}
            citations = []
            for ev in meta.get("evidence", [])[:3]:
                title = ev.get("source_title") or ev["source_id"]
                page = f"; PDF page {ev['pdf_page']}" if ev.get("pdf_page") else ""
                citations.append(f"{title}{page}")
            source_label = "; ".join(citations) or "Source metadata unavailable"
            status = meta.get("text_status", meta.get("review_status", "unreviewed"))
            label_budget = max(0, min(260, per_document // 2 - len(status) - 10))
            heading = f"[{number}] {source_label[:label_budget]} | {status}\n"
            budget = max(0, per_document - len(heading))
            parts.append(heading + document[:budget])
        return "\n\n".join(parts)[:max_chars]
