import re


class ContextCompressor:
    def is_clean_synonym(self, word: str) -> bool:
        word = word.strip()

        if len(word) < 2:
            return False

        if "(" in word or ")" in word:
            return False

        if " " in word:
            return False

        return True

    def compress(
        self,
        query: str,
        context: str,
        max_synonyms: int = 25,
        max_chars: int = 1200,
    ) -> str:
        query = query.strip()

        pattern = rf"{re.escape(query)}\s*[:ః]\s*([^.]*)"
        match = re.search(pattern, context)

        if match:
            entry = match.group(1).strip()

            synonyms = [
                word.strip()
                for word in entry.split(",")
                if word.strip() and self.is_clean_synonym(word.strip())
            ]

            synonyms = synonyms[:max_synonyms]

            return f"{query}: {', '.join(synonyms)}"

        parts = re.split(r"[.\n]+", context)

        selected = []
        for part in parts:
            part = part.strip()
            if query in part:
                selected.append(part)

        if selected:
            return "\n".join(selected)[:max_chars]

        return context[:max_chars]
