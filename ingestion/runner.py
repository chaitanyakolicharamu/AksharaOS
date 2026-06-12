import argparse

from ingestion.config import get_document_config, get_pdf_path
from ingestion.processors.ocr_processor import OCRProcessor
from ingestion.processors.clean_processor import CleanProcessor
from ingestion.processors.chunk_processor import ChunkProcessor
from ingestion.processors.synonym_chunk_processor import SynonymChunkProcessor
from ingestion.processors.dictionary_chunk_processor import DictionaryChunkProcessor
from ingestion.processors.quality_processor import QualityProcessor
from utils.logger import setup_logger

logger = setup_logger()


def run_document(document_id: str, start_page: int, end_page: int, force: bool = False):
    global_config, document_config = get_document_config(document_id)
    pdf_path = get_pdf_path(document_config)

    ocr_dir = f"data/interim/{document_id}/ocr_pages"
    clean_dir = f"data/interim/{document_id}/cleaned_pages"

    chunks_file = f"data/processed/{document_id}/chunks/chunks.jsonl"
    quality_file = f"data/curated/{document_id}/quality_chunks.jsonl"

    logger.info(f"Starting pipeline for document: {document_id}")
    logger.info(f"PDF: {pdf_path}")
    logger.info(f"Pages: {start_page} to {end_page}")
    logger.info(f"Chunk strategy: {document_config.chunk_strategy}")
    logger.info("[DONE] Pipeline completed for: {}", document_id)

    ocr = OCRProcessor(
        pdf_path=str(pdf_path),
        output_dir=ocr_dir,
        poppler_path=global_config.poppler_path,
        tesseract_path=global_config.tesseract_path,
        ocr_lang=document_config.ocr_lang,
    )
    ocr.run(start_page, end_page, force=force)

    cleaner = CleanProcessor(
        input_dir=ocr_dir,
        output_dir=clean_dir,
    )
    cleaner.run()

    if document_config.chunk_strategy == "synonym":
        chunker = SynonymChunkProcessor(
            input_dir=clean_dir,
            output_file=chunks_file,
            document_id=document_id,
        )
    elif document_config.chunk_strategy == "dictionary":
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

    print("=" * 80)
    print(f"[DONE] Pipeline completed for: {document_id}")
    print(f"[OUTPUT] {quality_file}")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Bangaru Palukulu config-driven ingestion runner"
    )

    parser.add_argument("--document", required=True)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--force", action="store_true")

    args = parser.parse_args()

    run_document(
        document_id=args.document,
        start_page=args.start,
        end_page=args.end,
        force=args.force,
    )


if __name__ == "__main__":
    main()
