import argparse
from pathlib import Path

from ingestion.processors.ocr_processor import OCRProcessor
from ingestion.processors.synonym_chunk_processor import SynonymChunkProcessor
from ingestion.processors.clean_processor import CleanProcessor
from ingestion.processors.chunk_processor import ChunkProcessor
from ingestion.processors.dictionary_chunk_processor import DictionaryChunkProcessor
from ingestion.processors.quality_processor import QualityProcessor

RAW_DICTIONARY_DIR = Path("data/raw/dictionaries")

POPPLER_PATH = r"C:\Users\venka\Downloads\Release-26.02.0-0\poppler-26.02.0\Library\bin"
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


DOCUMENTS = {
    "bangaru_nanelu": {
        "pdf": "bangaru_nanelu.pdf",
        "source_type": "dictionary_pdf",
        "ocr_lang": "tel",
    },
    "telugu_paryaya_nighantuvu": {
        "pdf": "telugu_paryaya.pdf",
        "source_type": "dictionary_pdf",
        "ocr_lang": "tel",
    },
    "telugu_english_dictionary": {
        "pdf": "telugu_english_dictionary.pdf",
        "source_type": "dictionary_pdf",
        "ocr_lang": "tel+eng",
    },
}


def run_document_pipeline(
    document_id: str, start_page: int, end_page: int, force: bool = False
):
    if document_id not in DOCUMENTS:
        raise ValueError(f"Unknown document_id: {document_id}")

    pdf_file = RAW_DICTIONARY_DIR / DOCUMENTS[document_id]["pdf"]

    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_file}")

    ocr_dir = f"data/interim/{document_id}/ocr_pages"
    clean_dir = f"data/interim/{document_id}/cleaned_pages"

    chunks_file = f"data/processed/{document_id}/chunks/chunks.jsonl"
    quality_file = f"data/curated/{document_id}/quality_chunks.jsonl"

    print("=" * 80)
    print(f"Starting pipeline for: {document_id}")
    print(f"PDF: {pdf_file}")
    print(f"OCR Language: {DOCUMENTS[document_id]['ocr_lang']}")
    print(f"Pages: {start_page} to {end_page}")
    print("=" * 80)

    ocr = OCRProcessor(
        pdf_path=str(pdf_file),
        output_dir=ocr_dir,
        poppler_path=POPPLER_PATH,
        tesseract_path=TESSERACT_PATH,
        ocr_lang=DOCUMENTS[document_id]["ocr_lang"],
    )
    ocr.run(start_page, end_page, force=force)

    cleaner = CleanProcessor(
        input_dir=ocr_dir,
        output_dir=clean_dir,
    )
    cleaner.run()

    if document_id == "telugu_paryaya_nighantuvu":
        chunker = SynonymChunkProcessor(
            input_dir=clean_dir,
            output_file=chunks_file,
            document_id=document_id,
        )

    elif document_id == "telugu_english_dictionary":
        chunker = DictionaryChunkProcessor(
            input_dir=clean_dir,
            output_file=chunks_file,
            document_id=document_id,
        )

    else:
        chunker = ChunkProcessor(
            input_dir=clean_dir,
            output_file=chunks_file,
            document_id=document_id,
        )

    chunker.run()

    quality = QualityProcessor(
        input_file=chunks_file,
        output_file=quality_file,
    )
    quality.run()

    print(f"Pipeline completed for: {document_id}")


def main():
    parser = argparse.ArgumentParser(
        description="Bangaru Palukulu multi-document ingestion pipeline"
    )

    parser.add_argument(
        "--document",
        type=str,
        required=True,
        choices=DOCUMENTS.keys(),
    )
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--force", action="store_true")

    args = parser.parse_args()

    run_document_pipeline(
        document_id=args.document,
        start_page=args.start,
        end_page=args.end,
        force=args.force,
    )


if __name__ == "__main__":
    main()
