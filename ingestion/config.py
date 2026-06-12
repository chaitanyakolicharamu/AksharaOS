from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

CONFIG_PATH = Path("configs/documents.yaml")
RAW_DICTIONARY_DIR = Path("data/raw/dictionaries")


class GlobalConfig(BaseModel):
    poppler_path: str
    tesseract_path: str


class DocumentConfig(BaseModel):
    pdf: str
    source_type: str
    source_role: str
    chunk_strategy: Literal["default", "synonym", "dictionary"]
    ocr_lang: str = "tel"


class AppConfig(BaseModel):
    global_config: GlobalConfig
    documents: dict[str, DocumentConfig]


def load_config(config_path: Path = CONFIG_PATH) -> AppConfig:
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as file:
        raw_config = yaml.safe_load(file)

    return AppConfig(
        global_config=GlobalConfig(**raw_config["global"]),
        documents={
            document_id: DocumentConfig(**document_data)
            for document_id, document_data in raw_config["documents"].items()
        },
    )


def get_document_config(document_id: str) -> tuple[GlobalConfig, DocumentConfig]:
    config = load_config()

    if document_id not in config.documents:
        available = ", ".join(config.documents.keys())
        raise ValueError(
            f"Unknown document_id: {document_id}. Available documents: {available}"
        )

    return config.global_config, config.documents[document_id]


def get_pdf_path(document_config: DocumentConfig) -> Path:
    pdf_path = RAW_DICTIONARY_DIR / document_config.pdf

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    return pdf_path
