from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from .rag import (
        available_passage_count,
        generate_general_answer,
        generate_grounded_answer,
        is_general_ai_configured,
        retrieve,
    )
except ImportError:
    # Vercel loads this module as app from the backend service root.
    from rag import (
        available_passage_count,
        generate_general_answer,
        generate_grounded_answer,
        is_general_ai_configured,
        retrieve,
    )

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


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=1200)


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    mode: Literal["trusted", "general"] = "trusted"
    history: list[ChatTurn] = Field(default_factory=list, max_length=10)


@app.get("/api/health")
def health() -> dict[str, int | str | bool]:
    return {
        "status": "ok",
        "indexed_passages": available_passage_count(),
        "general_ai_configured": is_general_ai_configured(),
    }


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict[str, object]:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Enter a question.")

    if request.mode == "general":
        if not is_general_ai_configured():
            raise HTTPException(
                status_code=503,
                detail=(
                    "General AI is not configured on the server. Add OPENAI_API_KEY "
                    "and OPENAI_MODEL in the Vercel project environment settings."
                ),
            )
        history = [
            {"role": turn.role, "content": turn.content}
            for turn in request.history
        ]
        try:
            answer = generate_general_answer(question, history)
        except Exception as error:
            raise HTTPException(
                status_code=502,
                detail=(
                    "General AI could not answer right now. Check the server's AI "
                    "provider configuration and try again."
                ),
            ) from error
        return {"answer": answer, "citations": [], "mode": "general"}

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
            "mode": "trusted",
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
            "mode": "trusted",
        }

    return {"answer": answer, "citations": valid_passages, "mode": "trusted"}
