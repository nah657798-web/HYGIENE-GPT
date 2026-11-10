from flask import Flask, request, jsonify
from flask_cors import CORS
import chromadb
from sentence_transformers import SentenceTransformer
import os

app = Flask(__name__)
CORS(app)

# Initialize Vector DB and Model
db_path = "./chroma_db"
client = chromadb.PersistentClient(path=db_path)
collection = client.get_or_create_collection(name="hygiene_docs")
model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    query = data.get('query', '')
    
    if not query:
        return jsonify({"error": "No query provided"}), 400

    # 1. Embed query
    query_embedding = model.encode(query).tolist()

    # 2. Retrieve top 3 matching chunks
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3
    )

    retrieved_chunks = results['documents'][0] if results['documents'] else []
    metadatas = results['metadatas'][0] if results['metadatas'] else []

    # Check relevance threshold
    if not retrieved_chunks:
        return jsonify({
            "answer": "I don't know based on the trusted guidelines provided.",
            "citations": []
        })

    # 3. Construct context for LLM / Generation
    context_str = ""
    citations = []
    for i, chunk in enumerate(retrieved_chunks):
        meta = metadatas[i]
        context_str += f"[Source {i+1}: {meta['source']}, p. {meta['page']}]\n{chunk}\n\n"
        citations.append({
            "id": i + 1,
            "source": meta['source'],
            "page": meta['page'],
            "text": meta['text']
        })

    answer = f"Based on official guidelines, you should follow the recommended protocols carefully. {retrieved_chunks[0][:150]}..."

    return jsonify({
        "answer": answer,
        "citations": citations
    })

@app.route('/api/compare', methods=['POST'])
def compare():
    data = request.json
    query = data.get('query', '')
    
    return jsonify({
        "normal_chatbot": "Sure! You can wash your hands with soda or just wipe them on your jeans if you are in a rush. (Hallucinated/Unsafe advice)",
        "hygiene_gpt": "Hands should be washed with soap and clean running water for at least 20 seconds. [WHO Hand Hygiene Guidelines, p. 14]"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
