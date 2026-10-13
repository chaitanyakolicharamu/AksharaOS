import re


def name_topic(query: str) -> str:
    """Remove common name-request wording, retaining the requested lexical topic.

    This is intentionally limited phrase handling. Complex constraints belong in
    the explicit /names fields, not an inferred natural-language parser.
    """
    request_words = set(
        "i we want need would like please suggest give me a an the some baby babies "
        "boy boys girl girls female females male males name names naming telugu pure "
        "with meaning meanings means of for related to and or in that which having "
        "ammayi ammayila abbayi abbayila peru perlu perulu accha achcha kavali cheppandi "
        "అచ్చ అచ్చతెలుగు తెలుగు అమ్మాయి అమ్మాయిల బాలిక అబ్బాయి అబ్బాయిల బాలుడు "
        "పేరు పేర్లు కోసం కావాలి చెప్పండి చూపించండి సూచించండి అర్థం అర్ధం అర్థము "
        "అర్ధము ఉన్న వంటి".split()
    )
    return " ".join(
        word
        for word in re.findall(r"[a-zA-Z]+|[\u0c00-\u0c7f]+", query.casefold())
        if word not in request_words
    )


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
