import os
from pypdf import PdfReader
import chromadb
from sentence_transformers import SentenceTransformer

def ingest_documents():
    db_path = "./chroma_db"
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_or_create_collection(name="hygiene_docs")

    # Load embedding model (multilingual support)
    model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')

    # Example document folder setup
    docs_dir = "./documents"
    if not os.path.exists(docs_dir):
        os.makedirs(docs_dir)
        print(f"Place your PDF files in {docs_dir}/ and re-run.")
        return

    chunk_id = 0
    for filename in os.listdir(docs_dir):
        if filename.endswith(".pdf"):
            pdf_path = os.path.join(docs_dir, filename)
            reader = PdfReader(pdf_path)
            
            for page_num, page in enumerate(reader.pages):
                text = page.extract_text()
                if not text.strip():
                    continue
                
                # Split text into 300-word chunks
                words = text.split()
                chunk_size = 300
                for i in range(0, len(words), chunk_size):
                    chunk_text = " ".join(words[i:i + chunk_size])
                    source_name = filename.replace(".pdf", "").replace("_", " ").title()
                    page_display = page_num + 1
                    
                    metadata = {
                        "source": source_name,
                        "page": page_display,
                        "text": chunk_text
                    }
                    
                    embedding = model.encode(chunk_text).tolist()
                    
                    collection.add(
                        embeddings=[embedding],
                        documents=[chunk_text],
                        metadatas=[metadata],
                        ids=[f"chunk_{chunk_id}"]
                    )
                    chunk_id += 1

    print(f"Successfully ingested {chunk_id} chunks into ChromaDB!")

if __name__ == "__main__":
    ingest_documents()
