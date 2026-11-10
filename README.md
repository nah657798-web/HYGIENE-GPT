# HygieneGPT

HygieneGPT is a source-grounded chatbot starter for hygiene questions. It searches trusted PDFs, answers from the retrieved passages, and returns clickable citations with the document name, PDF page, and exact passage.

This repository contains the application scaffold only. It does not include health guidance or source PDFs. Add documents from trusted organizations (such as WHO, CDC, or India's Ministry of Health and Family Welfare) before using it for a demonstration.

## Features

- PDF ingestion with page numbers retained in every chunk
- Multilingual semantic search using `intfloat/multilingual-e5-small`
- OpenAI Responses API for grounded answers; the API key stays on the server
- Refusal when the knowledge base is empty or no retrieved passage is relevant enough
- Clickable citations that highlight the supporting passage
- English and Tamil voice input/output using the browser's Web Speech API, when supported

## Project layout

```text
backend/
  app.py                 FastAPI endpoints
  ingest.py              PDF chunking and indexing
  rag.py                 Retrieval and grounded answer generation
  sources.json           Metadata for PDFs you add
  documents/             Put trusted PDF files here
  data/                  Local vector database (generated, not committed)
frontend/
  index.html
  styles.css
  app.js
.env.example
requirements.txt
```

## Run locally

Use Python 3.10 or newer.

1. Create and activate a virtual environment, then install dependencies:

   ```bash
   python -m venv .venv
   # Windows PowerShell: .venv\Scripts\Activate.ps1
   # macOS/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env`. Add your OpenAI API key and a model ID enabled for your account. Never put the key in frontend files or commit `.env`.

3. Add trusted, text-searchable PDFs to `backend/documents/`. Scanned image-only PDFs need OCR before ingestion.

4. Add each PDF's source details to `backend/sources.json`. The `filename` must match exactly:

   ```json
   {
     "documents": [
       {
         "filename": "hand-hygiene-guide.pdf",
         "title": "Hand hygiene guide",
         "organization": "World Health Organization",
         "year": "2023",
         "url": "https://www.who.int/"
       }
     ]
   }
   ```

   Replace the example URL and year with the actual document details. The included `sources.json` starts empty intentionally.

5. Build the local knowledge base:

   ```bash
   python -m backend.ingest
   ```

6. In one terminal, start the API from the repository root:

   ```bash
   uvicorn backend.app:app --reload
   ```

7. In another terminal, serve the frontend:

   ```bash
   python -m http.server 5173 --directory frontend
   ```

8. Open `http://127.0.0.1:5173` in your browser.

The first ingestion downloads the multilingual embedding model and may take a few minutes. Keep the API running while using the chat.

## How citations work

Each PDF page is split into overlapping chunks of roughly 280 words. The embedding index stores each chunk with its filename, organization, source URL, and one-based PDF page number. For a question, the backend retrieves the closest chunks and passes only those passages to the language model. The model must cite the supplied IDs (for example, `[S1]`); the UI links those IDs to the returned source passages.

Retrieval thresholds are a starting point, not a proof of accuracy. Adjust `RETRIEVAL_MAX_DISTANCE` after evaluating your own documents and test questions. Review citations and answers before presenting the project as health guidance.

## Configuration

See `.env.example` for the API key, model, retrieval count, distance threshold, and allowed frontend origins. The vector database and original PDFs are excluded from Git by default. Add only documents you are permitted to redistribute if you choose to publish them with the project.

## Scope and safety

HygieneGPT is an exhibition prototype, not a medical device or a substitute for professional advice. Its answers depend on the quality, coverage, and freshness of the PDFs you add. It should say when the documents do not contain an answer; it cannot guarantee that every generated claim or citation is correct. Do not use it for diagnosis or emergencies.

The OpenAI API is an external service. Review its current terms and privacy settings before sending questions or source passages to it. Keep credentials private and do not commit real user data.

## Evaluation

Use the blank question sheet and scoring guide in `evaluation/` to build and review a 30–50 question benchmark. The repository includes no claimed accuracy results; fill in the sheet using the source documents you choose.

