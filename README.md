# HygieneGPT 🩺🤖

An exhibition-ready RAG (Retrieval-Augmented Generation) chatbot that answers hygiene questions exclusively from trusted documents (WHO, CDC, Indian Health Ministry guidelines) with exact page citations.

## Features
- **Strict Grounding:** Answers only using retrieved chunks; refuses off-topic or unknown queries.
- **Click-to-Verify Citations:** Clicking a citation highlights the exact source passage.
- **Multilingual Support:** English and Tamil language queries matched against official guidelines.
- **Voice In/Out:** Powered by the browser's native Web Speech API.
- **Comparison Mode:** Side-by-side demo showing a normal hallucinating chatbot vs. HygieneGPT.

## Tech Stack
- **Frontend:** HTML5, Tailwind CSS, JavaScript (Web Speech API)
- **Backend:** Python, Flask, Flask-CORS
- **RAG & Vector Search:** ChromaDB, `sentence-transformers`
