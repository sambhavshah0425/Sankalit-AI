
from app.rag.document_loader import load_document
from app.rag.chunker import chunk_text
from app.rag.embedder import embed_chunks

print("SANKALIT INTELLIGENCE - EMBEDDING TEST")
print("--------------------------------------")

file_path = input("Enter PDF or DOCX path: ").strip().strip('"')

try:
    # Step 1: Extract document text
    document = load_document(file_path)

    # Step 2: Split document into chunks
    chunks = chunk_text(document["text"])

    print("\nTotal chunks:", len(chunks))
    print("Generating local embeddings...")

    # Step 3: Generate embeddings
    embedded_chunks = embed_chunks(chunks)

    print("\nEMBEDDING SUCCESSFUL")
    print("--------------------")
    print("Document:", document["filename"])
    print("Total embedded chunks:", len(embedded_chunks))
    print("Vector dimensions:", len(embedded_chunks[0]["embedding"]))
    print("First chunk index:", embedded_chunks[0]["chunk_index"])
    print("First chunk characters:", embedded_chunks[0]["character_count"])

    print("\nFirst 10 embedding values:")
    print(embedded_chunks[0]["embedding"][:10])

except Exception as error:
    print("\nEMBEDDING FAILED")
    print(error)
