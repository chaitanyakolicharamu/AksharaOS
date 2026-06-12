from ingestion.config import load_config, get_document_config


def test_load_config():
    config = load_config()

    assert config.global_config.poppler_path
    assert config.global_config.tesseract_path
    assert "bangaru_nanelu" in config.documents


def test_get_document_config():
    global_config, document_config = get_document_config("bangaru_nanelu")

    assert global_config.poppler_path
    assert document_config.pdf == "bangaru_nanelu.pdf"
    assert document_config.chunk_strategy == "default"
