from ingestion.processors.quality_processor import QualityProcessor


def test_telugu_ratio_high_for_telugu_text():
    processor = QualityProcessor(
        input_file="data/processed/test/chunks/chunks.jsonl",
        output_file="data/curated/test/quality_chunks.jsonl",
    )

    text = "పసికందు బిడ్డ శిశువు బాలుడు"
    assert processor.telugu_ratio(text) > 0.90


def test_digit_ratio_detects_numeric_junk():
    processor = QualityProcessor(
        input_file="data/processed/test/chunks/chunks.jsonl",
        output_file="data/curated/test/quality_chunks.jsonl",
    )

    text = "12345 ౧౨౩౪ 1118 40౮11101 తెలుగు"
    assert processor.digit_ratio(text) > 0.30


def test_telugu_word_count():
    processor = QualityProcessor(
        input_file="data/processed/test/chunks/chunks.jsonl",
        output_file="data/curated/test/quality_chunks.jsonl",
    )

    text = "పసికందు బిడ్డ శిశువు బాలుడు చిన్నవాడు"
    assert processor.telugu_word_count(text) == 5
