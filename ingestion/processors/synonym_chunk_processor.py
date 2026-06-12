from pathlib import Path
import json
import re


class SynonymChunkProcessor:
    def __init__(self, input_dir: str, output_file: str, document_id: str):
        self.input_dir = Path(input_dir)
        self.output_file = Path(output_file)
        self.document_id = document_id
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

    def get_page_number(self, file_path: Path) -> int:
        match = re.search(r"page_(\d+)", file_path.stem)
        return int(match.group(1)) if match else -1

    def split_entries(self, text: str):
        text = re.sub(r"\s+", " ", text).strip()

        # Match entries like:
        # 873. బిడ్డ: పసికందు, పసిపాప...
        pattern = r"(?=\b\d{1,4}\.\s*[\u0C00-\u0C7F][^:：]{0,80}[:：])"

        parts = re.split(pattern, text)

        entries = []

        for part in parts:
            part = part.strip()

            if not part:
                continue

            # Keep only entry-like text
            if not re.match(r"^\d{1,4}\.\s*[\u0C00-\u0C7F]", part):
                continue

            # Avoid very tiny fragments
            if len(part) < 40:
                continue

            entries.append(part)

        return entries

    def run(self):
        chunks = []

        files = sorted(self.input_dir.glob("page_*.txt"), key=self.get_page_number)

        for file_path in files:
            page_number = self.get_page_number(file_path)
            text = file_path.read_text(encoding="utf-8").strip()

            if not text:
                continue

            entries = self.split_entries(text)

            for idx, entry_text in enumerate(entries, start=1):
                chunks.append(
                    {
                        "document_id": self.document_id,
                        "source_type": "pdf",
                        "source_role": "synonym_dictionary",
                        "unit_type": "synonym_entry",
                        "unit_id": f"page_{page_number:03}_entry_{idx:03}",
                        "chunk_id": f"{self.document_id}_page_{page_number:03}_entry_{idx:03}",
                        "language": "te",
                        "text": entry_text,
                    }
                )

        with open(self.output_file, "w", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

        print(f"[SYNONYM CHUNK] Created {len(chunks)} chunks")
