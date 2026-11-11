from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb
from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent
DOCUMENTS_DIR = ROOT / "documents"
SOURCE_INDEX = ROOT / "sources.json"
load_dotenv(ROOT.parent / ".env")

COLLECTION_NAME = "hygienegpt_passages"
MODEL_NAME = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
TOP_K = max(1, min(int(os.getenv("TOP_K", "4")), 8))
MAX_DISTANCE = float(os.getenv("RETRIEVAL_MAX_DISTANCE", "0.75"))
TOKEN_PATTERN = re.compile(r"[a-z0-9]+|[\u0B80-\u0BFF]+", re.IGNORECASE)

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "can", "do", "does", "for",
    "from", "how", "i", "in", "is", "it", "me", "my", "of", "on", "or",
    "should", "the", "they", "to", "use", "using", "what", "when", "where",
    "which", "who", "why", "with", "you", "your",
}

DOMAIN_TERMS = {
    "hand", "hands", "wash", "washing", "handwash", "handwashing", "soap",
    "sanitizer", "sanitiser", "sanitizing", "sanitising", "hygiene", "clean",
    "cleaning", "rub", "abhr", "alcohol", "toilet", "bathroom", "restroom",
    "faeces", "feces", "poop", "cough", "coughing", "sneeze", "sneezing",
    "food", "eating", "eat", "feeding", "prepare", "preparing", "dirty",
    "water",
}

ALIAS_GROUPS = (
    {"wash", "washing", "handwash", "handwashing", "clean", "hygiene", "soap", "hands", "hand"},
    {"sanitizer", "sanitiser", "sanitizing", "sanitising", "handrub", "rub", "abhr", "alcohol"},
    {"seconds", "second", "duration", "long", "time", "dry"},
    {"toilet", "bathroom", "restroom", "faeces", "feces", "poop"},
    {"food", "eating", "eat", "feeding", "prepare", "preparing"},
    {"water", "running", "reliable", "soap"},
)

TAMIL_EXPANSIONS = {
    "கை": {"hand", "hands"},
    "கைகளை": {"hand", "hands"},
    "கழுவ": {"wash", "washing"},
    "கழுவுதல்": {"wash", "washing"},
    "சோப்பு": {"soap"},
    "தண்ணீர்": {"water"},
    "நீர்": {"water"},
    "சானிடைசர்": {"sanitizer", "alcohol", "rub"},
    "சுத்திகரிப்பான்": {"sanitizer", "rub"},
    "சுத்தம்": {"clean", "hygiene"},
    "சுகாதாரம்": {"hygiene"},
    "உணவு": {"food"},
    "கழிப்பறை": {"toilet"},
    "மலம்": {"faeces"},
    "இருமல்": {"cough"},
    "தும்மல்": {"sneeze"},
    "நேரம்": {"time", "seconds"},
    "எவ்வளவு": {"long", "duration"},
    "எப்போது": {"when"},
}


@lru_cache(maxsize=1)
def get_embedding_model() -> Any:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


@lru_cache(maxsize=1)
def get_collection() -> Any:
    configured_path = os.getenv("CHROMA_DATA_DIR")
    if configured_path:
        data_path = configured_path
    elif os.getenv("VERCEL"):
        # Vercel function bundles are read-only; /tmp is writable but ephemeral.
        data_path = str(Path("/tmp") / "hygienegpt-chroma")
    else:
        data_path = str(ROOT / "data")

    client = chromadb.PersistentClient(path=data_path)
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def _tokens(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN_PATTERN.findall(text)]


def _split_into_chunks(text: str, chunk_size: int = 240, overlap: int = 40) -> list[str]:
    normalized = re.sub(r"(?<=\w)-\s+(?=[a-z])", "", text, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    words = normalized.split()
    if not words:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap
    return chunks


@lru_cache(maxsize=1)
def get_bundled_passages() -> list[dict[str, Any]]:
    """Extract page-preserving chunks from the PDF files listed in sources.json."""
    try:
        source_data = json.loads(SOURCE_INDEX.read_text(encoding="utf-8"))
        documents = source_data.get("documents", [])
    except (OSError, json.JSONDecodeError):
        return []

    try:
        from pypdf import PdfReader
    except ImportError:
        return []

    passages: list[dict[str, Any]] = []
    documents_root = DOCUMENTS_DIR.resolve()

    for source in documents:
        filename = str(source.get("filename", "")).strip()
        if not filename or Path(filename).name != filename or not filename.lower().endswith(".pdf"):
            continue

        pdf_path = (DOCUMENTS_DIR / filename).resolve()
        if pdf_path.parent != documents_root or not pdf_path.is_file():
            continue

        try:
            reader = PdfReader(str(pdf_path))
        except Exception:
            continue

        for page_number, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception:
                continue

            for chunk in _split_into_chunks(page_text):
                passages.append(
                    {
                        "text": chunk,
                        "source": source.get("title") or filename,
                        "organization": source.get("organization", ""),
                        "year": source.get("year", ""),
                        "url": source.get("url", ""),
                        "page": page_number,
                    }
                )

    return passages


def _question_terms(question: str) -> set[str]:
    terms = {
        token
        for token in _tokens(question)
        if len(token) > 1 and token not in STOPWORDS
    }
    lowered = question.casefold()
    for tamil_phrase, english_terms in TAMIL_EXPANSIONS.items():
        if tamil_phrase in lowered:
            terms.update(english_terms)
    return terms


def _has_hygiene_scope(question_terms: set[str]) -> bool:
    return bool(question_terms.intersection(DOMAIN_TERMS))


def _keyword_retrieve(question: str) -> list[dict[str, Any]]:
    query_terms = _question_terms(question)
    if not query_terms or not _has_hygiene_scope(query_terms):
        return []

    aliases: set[str] = set()
    for group in ALIAS_GROUPS:
        if query_terms.intersection(group):
            aliases.update(group - query_terms)

    scored: list[tuple[float, dict[str, Any]]] = []
    for passage in get_bundled_passages():
        passage_terms = set(_tokens(passage["text"]))
        direct_matches = query_terms.intersection(passage_terms)
        alias_matches = aliases.intersection(passage_terms)
        weighted_matches = len(direct_matches) + 0.25 * len(alias_matches)
        denominator = max(1.0, len(query_terms) + 0.25 * len(aliases))
        score = weighted_matches / denominator

        if score >= 0.08:
            scored.append((score, passage))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "citation_id": f"S{index}",
            "text": passage["text"],
            "distance": round(1.0 - score, 4),
            "source": passage["source"],
            "organization": passage["organization"],
            "year": passage["year"],
            "url": passage["url"],
            "page": int(passage["page"]),
        }
        for index, (score, passage) in enumerate(scored[:TOP_K], start=1)
    ]


def _semantic_retrieve(question: str) -> list[dict[str, Any]]:
    collection = get_collection()
    count = collection.count()
    if count == 0:
        return []

    model = get_embedding_model()
    query_vector = model.encode(
        f"query: {question}",
        normalize_embeddings=True,
    ).tolist()
    result = collection.query(
        query_embeddings=[query_vector],
        n_results=min(TOP_K, count),
        include=["documents", "metadatas", "distances"],
    )

    passages: list[dict[str, Any]] = []
    documents = result.get("documents", [[]])[0]
    metadata_rows = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    for index, (text, metadata, distance) in enumerate(
        zip(documents, metadata_rows, distances), start=1
    ):
        if text and distance <= MAX_DISTANCE:
            passages.append(
                {
                    "citation_id": f"S{index}",
                    "text": text,
                    "distance": float(distance),
                    "source": metadata.get("title") or metadata.get("source_file", "Unknown PDF"),
                    "organization": metadata.get("organization", ""),
                    "year": metadata.get("year", ""),
                    "url": metadata.get("url", ""),
                    "page": int(metadata.get("page", 1)),
                }
            )
    return passages


def retrieve(question: str) -> list[dict[str, Any]]:
    # Keep the local semantic index when available. If it is empty, unavailable,
    # or finds no close passage, search the PDFs bundled with the deployed app.
    try:
        passages = _semantic_retrieve(question)
        if passages:
            return passages
    except Exception:
        pass
    return _keyword_retrieve(question)


def available_passage_count() -> int:
    try:
        count = get_collection().count()
        if count:
            return int(count)
    except Exception:
        pass
    return len(get_bundled_passages())


def _extractive_answer(passages: list[dict[str, Any]]) -> str:
    passage = passages[0]
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", passage["text"])
        if sentence.strip()
    ]
    if not sentences:
        excerpt = " ".join(passage["text"].split()[:45])
    else:
        excerpt = sentences[0]
    words = excerpt.split()
    if len(words) > 45:
        excerpt = " ".join(words[:45]).rstrip(" ,;:") + "..."
    return f'The trusted document says: "{excerpt}" [{passage["citation_id"]}]'


def generate_grounded_answer(question: str, passages: list[dict[str, Any]]) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model_name = os.getenv("OPENAI_MODEL", "").strip()
    if not api_key or not model_name or model_name == "your-enabled-model-id":
        return _extractive_answer(passages)

    evidence = "\n\n".join(
        f"[{passage['citation_id']}] {passage['source']} — PDF page {passage['page']}\n"
        f"{passage['text']}"
        for passage in passages
    )

    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=model_name,
            instructions=(
                "You are HygieneGPT, a careful assistant for general hygiene education. "
                "Answer only with information supported by the supplied evidence. "
                "Do not use outside knowledge or make up facts. Cite every factual claim "
                "with one or more exact evidence IDs in square brackets, such as [S1]. "
                "Never invent or alter an evidence ID. If the evidence does not answer "
                "the question, say that you do not know based on the available documents. "
                "Reply in the same language as the user's question when possible, including Tamil. "
                "If the user asks for diagnosis, treatment, or emergency help, do not diagnose; "
                "state that this tool cannot assess their situation and direct them to a qualified "
                "health professional or local emergency services as appropriate. Keep the answer concise."
            ),
            input=(
                f"Question:\n{question}\n\n"
                f"Retrieved evidence (the only permitted source of factual claims):\n{evidence}"
            ),
            max_output_tokens=450,
        )
        answer = response.output_text.strip()
        return answer or _extractive_answer(passages)
    except Exception:
        # Keep source lookup useful if the hosted model is temporarily unavailable.
        return _extractive_answer(passages)
