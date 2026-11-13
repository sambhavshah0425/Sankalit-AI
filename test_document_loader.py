from app.rag.document_loader import load_document

print("Document Loader Test")
print("--------------------")

file_path = input("Enter the full path of a PDF or DOCX file: ").strip().strip('"')

try:
    result = load_document(file_path)

    print("\nDocument processed successfully!")
    print("Filename:", result["filename"])
    print("File type:", result["file_type"])
    print("Character count:", result["character_count"])

    print("\nExtracted text preview:")
    print(result["text"][:1000])

except Exception as error:
    print("\nDocument processing failed:")
    print(error)