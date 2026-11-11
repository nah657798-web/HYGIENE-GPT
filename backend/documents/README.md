# Trusted source PDFs

This folder includes two reviewed community hand-hygiene references: the 2025 WHO/UNICEF guideline and the 2022 CDC hand-cleaning factsheet. They are extracted directly at runtime, so Vercel does not need a prebuilt or persistent vector database for the bundled documents.

Before adding another PDF, check its date, exact reuse terms, text-searchability and scope. Add its exact filename and source metadata to ../sources.json. Scanned PDFs need OCR before the app can search their text. See ../SOURCES-LICENSES.md for the bundled sources and attribution.
