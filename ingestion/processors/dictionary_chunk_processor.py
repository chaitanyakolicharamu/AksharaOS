from pathlib import Path
import json
import re


class DictionaryChunkProcessor:
    def __init__(self, input_dir: str, output_file: str, document_id: str):
        self.input_dir = Path(input_dir)
        self.output_file = Path(output_file)
        self.document_id = document_id
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

    def get_page_number(self, file_path: Path) -> int:
        match = re.search(r"page_(\d+)", file_path.stem)
        return int(match.group(1)) if match else -1

    def split_dictionary_entries(self, text: str):
        """
        First version:
        Splits dictionary OCR text into entry-like chunks.
        Later we can improve after seeing actual OCR format.
        """

        # Normalize spaces
        text = re.sub(r"\s+", " ", text).strip()

        # Split around Telugu alphabetical entry patterns or punctuation
        # This is intentionally conservative.
        parts = re.split(r"(?<=[.!?।])\s+|(?=\s*[\u0C00-\u0C7F]{2,}\s*[:\-])", text)

        entries = []

        buffer = ""

        for part in parts:
            part = part.strip()

            if not part:
                continue

            # If buffer becomes large, flush it
            if len(buffer) + len(part) > 500:
                if buffer:
                    entries.append(buffer.strip())
                buffer = part
            else:
                buffer += " " + part

        if buffer:
            entries.append(buffer.strip())

        return entries

    def run(self):
        chunks = []

        files = sorted(self.input_dir.glob("page_*.txt"), key=self.get_page_number)

        for file_path in files:
            page_number = self.get_page_number(file_path)
            text = file_path.read_text(encoding="utf-8").strip()

            if not text:
                continue

            entries = self.split_dictionary_entries(text)

            for idx, entry_text in enumerate(entries, start=1):
                if len(entry_text) < 40:
                    continue

                chunks.append(
                    {
                        "document_id": self.document_id,
                        "source_type": "pdf",
                        "source_role": "meaning_dictionary",
                        "unit_type": "dictionary_entry",
                        "unit_id": f"page_{page_number:03}_entry_{idx:03}",
                        "chunk_id": f"{self.document_id}_page_{page_number:03}_entry_{idx:03}",
                        "language": "te",
                        "text": entry_text,
                    }
                )

        with open(self.output_file, "w", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

        print(f"[DICTIONARY CHUNK] Created {len(chunks)} chunks")
