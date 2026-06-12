from pathlib import Path
import pytesseract
from pdf2image import convert_from_path


class OCRProcessor:
    def __init__(
        self, pdf_path, output_dir, poppler_path, tesseract_path, ocr_lang="tel"
    ):
        self.pdf_path = pdf_path
        self.output_dir = Path(output_dir)
        self.poppler_path = poppler_path
        self.tesseract_path = tesseract_path
        self.ocr_lang = ocr_lang

        pytesseract.pytesseract.tesseract_cmd = self.tesseract_path

    def run(self, start_page: int, end_page: int, force: bool = False):
        self.output_dir.mkdir(parents=True, exist_ok=True)

        for page_number in range(start_page, end_page + 1):
            output_file = self.output_dir / f"page_{page_number:03d}.txt"

            if output_file.exists() and not force:
                print(f"[OCR] Skipping page {page_number}, already exists.")
                continue

            print(f"[OCR] Processing page {page_number}...")

            pages = convert_from_path(
                self.pdf_path,
                first_page=page_number,
                last_page=page_number,
                dpi=300,
                poppler_path=self.poppler_path,
            )

            image = pages[0]

            text = pytesseract.image_to_string(
                image,
                lang=self.ocr_lang,
            )

            with open(output_file, "w", encoding="utf-8") as file:
                file.write(text)

            print(f"[OCR] Saved {output_file}")
