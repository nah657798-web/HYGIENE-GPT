from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from backend.rag import COLLECTION_NAME, ROOT, get_collection, get_embedding_model

DOCUMENTS_DIR = ROOT / "documents"
MANIFEST_PATH = ROOT / "sources.json"
WORDS_PER_CHUNK = 280
OVERLAP_WORDS = 45


def load_manifest() -> dict[str, dict[str, str]]:
    if not MANIFEST_PATH.exists():
        return {}
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {
        item["filename"]: item
        for item in data.get("documents", [])
        if item.get("filename")
    }


def split_into_chunks(text: str) -> list[str]:
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    step = WORDS_PER_CHUNK - OVERLAP_WORDS
    for start in range(0, len(words), step):
        chunk = " ".join(words[start : start + WORDS_PER_CHUNK]).strip()
        if chunk:
            chunks.append(chunk)
        if start + WORDS_PER_CHUNK >= len(words):
            break
    return chunks


def safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")[:180]


def index_pdf(pdf_path: Path, manifest: dict[str, str]) -> tuple[int, int]:
    reader = PdfReader(str(pdf_path))
    collection = get_collection()
    source_file = pdf_path.name

    collection.delete(where={"source_file": source_file})

    model = get_embedding_model()
    ids: list[str] = []
    texts: list[str] = []
    metadatas: list[dict[str, Any]] = []
    skipped_pages = 0

    for page_number, page in enumerate(reader.pages, start=1):
        page_text = (page.extract_text() or "").strip()
        if not page_text:
            skipped_pages += 1
            continue

        for chunk_number, chunk in enumerate(split_into_chunks(page_text), start=1):
            chunk_id = safe_id(f"{source_file}-{page_number}-{chunk_number}")
            ids.append(chunk_id)
            texts.append(chunk)
            metadatas.append(
                {
                    "source_file": source_file,
                    "title": manifest.get("title", pdf_path.stem),
                    "organization": manifest.get("organization", ""),
                    "year": manifest.get("year", ""),
                    "url": manifest.get("url", ""),
                    "page": page_number,
                }
            )

    if texts:
        vectors = model.encode(
            [f"passage: {text}" for text in texts],
            normalize_embeddings=True,
            show_progress_bar=False,
        ).tolist()
        collection.add(
            ids=ids,
            documents=texts,
            metadatas=metadatas,
            embeddings=vectors,
        )
    return len(texts), skipped_pages


def main() -> None:
    pdfs = sorted(DOCUMENTS_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {DOCUMENTS_DIR}.")
        print("Add trusted PDFs, update backend/sources.json, then run ingestion again.")
        return

    manifest = load_manifest()
    total_chunks = 0
    for pdf_path in pdfs:
        try:
            chunks, skipped_pages = index_pdf(pdf_path, manifest.get(pdf_path.name, {}))
            total_chunks += chunks
            print(
                f"Indexed {pdf_path.name}: {chunks} chunks; "
                f"{skipped_pages} pages had no extractable text."
            )
        except Exception as error:
            print(f"Could not index {pdf_path.name}: {error}")

    print(f"Done. Indexed {total_chunks} chunks in '{COLLECTION_NAME}'.")
    print("If a PDF is scanned, OCR it first and run this command again.")


if __name__ == "__main__":
    main()
