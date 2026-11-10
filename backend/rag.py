from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb
from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT.parent / ".env")

COLLECTION_NAME = "hygienegpt_passages"
MODEL_NAME = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
TOP_K = max(1, min(int(os.getenv("TOP_K", "4")), 8))
MAX_DISTANCE = float(os.getenv("RETRIEVAL_MAX_DISTANCE", "0.75"))


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


def retrieve(question: str) -> list[dict[str, Any]]:
    collection = get_collection()
    if collection.count() == 0:
        return []

    model = get_embedding_model()
    query_vector = model.encode(
        f"query: {question}",
        normalize_embeddings=True,
    ).tolist()
    result = collection.query(
        query_embeddings=[query_vector],
        n_results=min(TOP_K, collection.count()),
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


def generate_grounded_answer(question: str, passages: list[dict[str, Any]]) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model_name = os.getenv("OPENAI_MODEL", "").strip()
    if not api_key or not model_name or model_name == "your-enabled-model-id":
        raise RuntimeError(
            "Set OPENAI_API_KEY and OPENAI_MODEL in your .env file to enable answers."
        )

    evidence = "\n\n".join(
        f"[{passage['citation_id']}] {passage['source']} — page {passage['page']}\n"
        f"{passage['text']}"
        for passage in passages
    )

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
    return response.output_text.strip()
