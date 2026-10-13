import re


class QueryRouter:
    def detect_mode(self, query: str) -> str:
        pure_telugu_terms = ["అచ్చ", "అచ్చతెలుగు", "తెలుగు మాట", "సాటి మాట"]
        name_terms = ["పేర్లు", "పేరు", "అమ్మాయిల", "అబ్బాయిల"]

        if any(term in query for term in name_terms) or re.search(
            r"\b(names?|naming|peru|perlu|perulu|ammayi|ammayila|abbayi|abbayila)\b",
            query.casefold(),
        ):
            return "name"

        if any(term in query for term in pure_telugu_terms):
            return "pure_telugu"

        return "synonym"
