from pathlib import Path
import re
import unicodedata


class CleanProcessor:
    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def clean_text(self, text: str) -> str:
        text = unicodedata.normalize("NFC", text)

        text = re.sub(r"[^\u0C00-\u0C7Fa-zA-Z0-9\s.,;:!?()\-/₹%]", " ", text)

        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    def run(self):
        for file_path in sorted(self.input_dir.glob("page_*.txt")):
            raw_text = file_path.read_text(encoding="utf-8")
            cleaned_text = self.clean_text(raw_text)

            output_file = self.output_dir / file_path.name
            output_file.write_text(cleaned_text, encoding="utf-8")

            print(f"[CLEAN] Cleaned {file_path.name}")
