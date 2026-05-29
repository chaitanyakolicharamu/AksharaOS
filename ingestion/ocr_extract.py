from pdf2image import convert_from_path
import pytesseract
from pathlib import Path

pdf_path = "data/raw/dictionaries/bangaru_nanelu.pdf"

poppler_path = r"C:\Users\venka\Downloads\Release-26.02.0-0\poppler-26.02.0\Library\bin"

output_dir = Path("data/processed/dictionaries/ocr_pages")
output_dir.mkdir(parents=True, exist_ok=True)

pages = convert_from_path(
    pdf_path,
    dpi=300,
    poppler_path=poppler_path
)

for i, page in enumerate(pages):
    text = pytesseract.image_to_string(page, lang="tel")

    output_file = output_dir / f"page_{i+1}.txt"
    output_file.write_text(text, encoding="utf-8")

    print(f"OCR completed for page {i+1}")

print("OCR extraction finished.")