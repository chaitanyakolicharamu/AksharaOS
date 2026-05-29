import fitz
from pathlib import Path

pdf_path = Path("data/raw/dictionaries/bangaru_nanelu.pdf")

doc = fitz.open(pdf_path)

output_dir = Path("data/processed/dictionaries/raw_pages")
output_dir.mkdir(parents=True, exist_ok=True)

for i, page in enumerate(doc):
    text = page.get_text()

    output_file = output_dir / f"page_{i+1}.txt"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"Extracted page {i+1}")

print("Done.")