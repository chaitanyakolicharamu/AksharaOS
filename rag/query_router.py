class QueryRouter:
    def detect_mode(self, query: str) -> str:
        pure_telugu_terms = ["అచ్చ", "అచ్చతెలుగు", "తెలుగు మాట", "సాటి మాట"]
        name_terms = ["పేర్లు", "పేరు", "అమ్మాయిల", "అబ్బాయిల"]

        if any(term in query for term in pure_telugu_terms):
            return "pure_telugu"

        if any(term in query for term in name_terms):
            return "name"

        return "synonym"
