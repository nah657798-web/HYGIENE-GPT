# HygieneGPT

HygieneGPT is a source-grounded chatbot for community hygiene questions. It searches trusted PDFs, shows the exact source passage and PDF page, and refuses when the available documents do not support an answer.

## Included reference documents

- WHO and UNICEF, Guidelines on hand hygiene in community settings (2025): evidence-based recommendations for homes, public places and institutions.
- CDC, When and How to Clean Hands (2022): a concise handwashing and hand-sanitizer guide.

The documents are stored in backend/documents/ and their source details and reuse terms are listed in backend/sources.json and backend/SOURCES-LICENSES.md. This small collection focuses on hand hygiene. It is not a complete medical library and does not cover diagnosis, treatment, clinical care, full food-safety guidance or drinking-water quality.

## Features

- PDF text extraction that retains one-based page numbers for citations
- Semantic search with the local ChromaDB index when it is available
- Bundled-PDF keyword search as a deployment fallback, so Vercel can answer without a prebuilt or persistent vector database
- Separate Trusted Hygiene mode with PDF citations and source-grounded answers
- Separate General AI mode for broader conversation through the server-side OpenAI Responses API; general answers are clearly uncited
- General AI mode stays unavailable until OPENAI_API_KEY and OPENAI_MODEL are configured on the server
- Refusal in Trusted Hygiene mode when a question is outside the available source passages
- Clickable citations that highlight the supporting passage
- English and Tamil voice input and output through the browser Web Speech API when supported

## Answer modes

The website has two modes. **Trusted hygiene** answers only from the bundled WHO/UNICEF and CDC PDFs and shows citations. **General AI** can answer broader topics using the OpenAI API; those answers are not checked against the PDFs and are labeled uncited. General AI gives general health education only and does not diagnose or prescribe.

The frontend never receives the provider key. Until the server has both OPENAI_API_KEY and OPENAI_MODEL configured, General AI mode shows that setup is needed and the API returns a clear configuration error.

## Project layout

    backend/
      app.py                 FastAPI endpoints
      ingest.py              Local PDF chunking and vector indexing
      rag.py                 Retrieval and grounded answer generation
      sources.json           Metadata for bundled PDFs
      SOURCES-LICENSES.md    Source attribution and reuse terms
      documents/             Bundled trusted PDFs
      data/                  Local vector database, generated and not committed
    frontend/
      index.html
      styles.css
      app.js
    .env.example
    requirements.txt

## Run locally

Use Python 3.10 or newer.

1. Create and activate a virtual environment, then install dependencies:

       python -m venv .venv
       # Windows PowerShell: .venv\Scripts\Activate.ps1
       # macOS/Linux: source .venv/bin/activate
       pip install -r requirements.txt

2. Copy .env.example to .env. Add an OpenAI API key and a model ID enabled for your account if you want generated answers. Never put the key in frontend files or commit .env.

3. The bundled documents are ready to search. To add a PDF, confirm that redistribution is permitted, place it in backend/documents/, and add its exact filename and source metadata to backend/sources.json.

4. To build the optional local semantic index, run:

       python -m backend.ingest

5. Start the API from the repository root:

       uvicorn backend.app:app --reload

6. In another terminal, serve the frontend:

       python -m http.server 5173 --directory frontend

7. Open http://127.0.0.1:5173 in your browser.

The first local semantic indexing run downloads the multilingual embedding model and may take a few minutes. Bundled-PDF keyword search works without that index.

## Deploy on Vercel

The included vercel.json routes the frontend and FastAPI backend through one Vercel project. The deployed frontend calls same-domain /api routes; local development calls http://127.0.0.1:8000.

The API reads the bundled PDFs directly and extracts their page text on first use. In the Vercel project settings, add OPENAI_API_KEY and OPENAI_MODEL as environment variables for the server. General AI mode is enabled when both are present; its key stays server-side. Without them, trusted hygiene mode still works with cited excerpts, while General AI mode reports that server setup is needed.

## How citations work

Each PDF page is split into overlapping chunks of about 240 words. Every chunk retains its document title, organization, source URL and one-based PDF page. The backend retrieves relevant chunks and passes only those passages to the language model. Each factual statement must cite an exact evidence ID such as [S1]. The UI links the citation to the supporting passage and source document.

Search quality depends on the documents and retrieval settings. Review answers and citations before presenting the project as health guidance. Do not claim an accuracy score until you have measured it with a reviewed benchmark.

## Configuration

See .env.example for the API key, model, retrieval count, distance threshold and allowed frontend origins. Only selected PDFs with reviewed reuse rights should be committed. Do not commit .env or personal health information.

## Scope and safety

HygieneGPT is an exhibition prototype, not a medical device or a substitute for professional advice. Trusted Hygiene mode is limited to the bundled hand-hygiene documents. General AI mode uses an uncited language model and can be wrong; it does not diagnose, prescribe or handle emergencies. Seek qualified care for personal medical concerns and local emergency services for emergencies.

Questions and retrieved source passages may be sent to OpenAI when the API is configured. Review the provider's current terms and privacy settings before use. Keep credentials private.

## Evaluation

Use the blank question sheet and scoring guide in evaluation/ to create and review a 30–50 question benchmark. The repository makes no accuracy claim; fill in the sheet only after scoring against the source documents.
