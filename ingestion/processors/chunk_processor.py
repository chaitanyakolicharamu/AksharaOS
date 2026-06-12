from pathlib import Path
import json
import re


class ChunkProcessor:
    def __init__(self, input_dir: str, output_file: str, document_id: str):
        self.input_dir = Path(input_dir)
        self.output_file = Path(output_file)
        self.document_id = document_id
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

    def get_page_number(self, file_path: Path) -> int:
        match = re.search(r"page_(\d+)", file_path.stem)
        return int(match.group(1)) if match else -1

    def run(self, chunk_size: int = 500):
        chunks = []

        files = sorted(self.input_dir.glob("page_*.txt"), key=self.get_page_number)

        for file_path in files:
            page_number = self.get_page_number(file_path)
            text = file_path.read_text(encoding="utf-8").strip()

            if not text:
                continue

            text_chunks = [
                text[i : i + chunk_size] for i in range(0, len(text), chunk_size)
            ]

            for idx, chunk_text in enumerate(text_chunks, start=1):
                chunks.append(
                    {
                        "document_id": self.document_id,
                        "source_type": "pdf",
                        "unit_type": "page",
                        "unit_id": f"page_{page_number:03}",
                        "chunk_id": f"{self.document_id}_page_{page_number:03}_chunk_{idx:03}",
                        "language": "te",
                        "text": chunk_text.strip(),
                    }
                )

        with open(self.output_file, "w", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

        print(f"[CHUNK] Created {len(chunks)} chunks")
