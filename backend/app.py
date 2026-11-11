from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from .rag import available_passage_count, generate_grounded_answer, retrieve
except ImportError:
    # Vercel loads this module as app from the backend service root.
    from rag import available_passage_count, generate_grounded_answer, retrieve

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT.parent / ".env")

app = FastAPI(title="HygieneGPT API", version="0.1.0")
origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)


@app.get("/api/health")
def health() -> dict[str, int | str]:
    return {"status": "ok", "indexed_passages": available_passage_count()}


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict[str, object]:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Enter a question.")

    try:
        passages = retrieve(question)
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"The trusted PDF library could not be searched: {error}",
        ) from error

    if not passages:
        return {
            "answer": "I couldn't find support for that in the current hand-hygiene references. Try asking about handwashing, soap, sanitizer, or when to clean hands.",
            "citations": [],
        }

    try:
        answer = generate_grounded_answer(question, passages)
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail="The answer service is unavailable. Check the server configuration and try again.",
        ) from error

    cited_ids = set(re.findall(r"\[(S\d+)\]", answer))
    retrieved_ids = {passage["citation_id"] for passage in passages}
    valid_passages = [
        passage for passage in passages if passage["citation_id"] in cited_ids
    ]
    # If the answer omits citations or invents an ID, refuse rather than show an unverified answer.
    if not valid_passages or not cited_ids.issubset(retrieved_ids):
        return {
            "answer": "I couldn't find support for that in the current hand-hygiene references. Try asking about handwashing, soap, sanitizer, or when to clean hands.",
            "citations": [],
        }

    return {"answer": answer, "citations": valid_passages}
