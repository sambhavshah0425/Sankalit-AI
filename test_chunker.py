
from app.rag.document_loader import load_document
from app.rag.chunker import chunk_text

file_path = input("Enter your PDF or DOCX path: ").strip().strip('"')

try:
    document = load_document(file_path)

    chunks = chunk_text(document["text"])

    print("\nCHUNKING SUCCESSFUL")
    print("-------------------")
    print("Filename:", document["filename"])
    print("Total characters:", document["character_count"])
    print("Total chunks:", len(chunks))

    for chunk in chunks[:3]:
        print("\nChunk:", chunk["chunk_index"])
        print("Characters:", chunk["character_count"])
        print("Preview:")
        print(chunk["text"][:300])
        print("-" * 50)

except Exception as error:
    print("Error:", error)
