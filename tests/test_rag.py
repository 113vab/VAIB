import tempfile
import shutil
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Create a temporary directory for tests
@pytest.fixture(scope="module", autouse=True)
def test_rag_env():
    temp_dir = tempfile.mkdtemp()
    
    # Patch config variables before importing models
    with patch("app.config.DATA_DIR", Path(temp_dir)), \
         patch("app.config.CHROMA_DB_PATH", str(Path(temp_dir) / "chroma")):
        from app.brain.memory import MemoryManager
        from app.brain.rag import DocumentIngestionPipeline, chunk_text
        from app.tools.rag_parsers import extract_document_content
        
        memory = MemoryManager()
        pipeline = DocumentIngestionPipeline(memory)
        
        yield {
            "temp_dir": Path(temp_dir),
            "memory": memory,
            "pipeline": pipeline,
            "chunk_text": chunk_text,
            "extract_content": extract_document_content
        }
        
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass

def test_semantic_chunking(test_rag_env):
    chunk_fn = test_rag_env["chunk_text"]
    
    # Text smaller than chunk size
    short_text = "Hello world. This is a RAG test."
    chunks = chunk_fn(short_text, chunk_size=100)
    assert len(chunks) == 1
    assert chunks[0] == short_text
    
    # Text larger than chunk size splitting recursively on paragraphs/sentences
    long_text = "\n\n".join([f"Paragraph turn content number {i} showing sentence boundaries." for i in range(10)])
    chunks = chunk_fn(long_text, chunk_size=80, chunk_overlap=10)
    assert len(chunks) > 1
    # Verify each chunk is bounded by chunk_size
    for chunk in chunks:
        assert len(chunk) <= 120  # paragraph split leeway

def test_document_ingestion_pipeline_txt(test_rag_env):
    env = test_rag_env
    memory = env["memory"]
    pipeline = env["pipeline"]
    
    # Create temp text file
    temp_txt = env["temp_dir"] / "test_report.txt"
    content = "V.A.I.B. (Virtual Artificial Intelligence Brain) is an advanced voice assistant running locally on Windows. It manages reminders, calendar syncs, and custom plugins."
    temp_txt.write_text(content, encoding="utf-8")
    
    # Ingest document
    import asyncio
    result = asyncio.run(pipeline.ingest_document(temp_txt))
    
    assert result["source"] == "test_report.txt"
    assert result["chunk_count"] > 0
    
    # Query knowledge base
    query_matches = memory.query_documents("What does VAIB stand for?")
    assert len(query_matches) > 0
    assert query_matches[0]["metadata"]["source"] == "test_report.txt"
    assert "Virtual Artificial Intelligence Brain" in query_matches[0]["text"]
    
    # Check indexed documents library
    indexed_library = memory.get_indexed_documents()
    assert len(indexed_library) == 1
    assert indexed_library[0]["source"] == "test_report.txt"
    assert indexed_library[0]["chunk_count"] > 0
    
    # Delete document
    success = memory.delete_document_by_source("test_report.txt")
    assert success is True
    
    # Library should be empty now
    assert len(memory.get_indexed_documents()) == 0

def test_pdf_docx_parser_routing(test_rag_env):
    extract_fn = test_rag_env["extract_content"]
    
    # Test routing error on unsupported formats
    unsupported_path = test_rag_env["temp_dir"] / "dummy.png"
    unsupported_path.write_text("dummy", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported file format"):
         extract_fn(unsupported_path)
         
    # Mock extract_text_from_pdf and docx to verify routing
    with patch("app.tools.rag_parsers.extract_text_from_pdf", return_value="PDF mock contents") as mock_pdf, \
         patch("app.tools.rag_parsers.extract_text_from_docx", return_value="DOCX mock contents") as mock_docx:
         
         pdf_path = test_rag_env["temp_dir"] / "test.pdf"
         pdf_path.write_text("dummy", encoding="utf-8")
         docx_path = test_rag_env["temp_dir"] / "test.docx"
         docx_path.write_text("dummy", encoding="utf-8")
         
         res_pdf = extract_fn(pdf_path)
         assert res_pdf == "PDF mock contents"
         mock_pdf.assert_called_once_with(pdf_path)
         
         res_docx = extract_fn(docx_path)
         assert res_docx == "DOCX mock contents"
         mock_docx.assert_called_once_with(docx_path)
