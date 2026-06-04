import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.brain.memory import MemoryManager
from app.tools.rag_parsers import extract_document_content

logger = logging.getLogger("vaib")

def chunk_text(text: str, chunk_size: int = 600, chunk_overlap: int = 100) -> List[str]:
    """
    Splits document text into chunks semantic-style by paragraph/sentence breaks.
    Maintains a maximum target length with character index fallback when paragraphs are oversized.
    """
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
            
        if len(para) > chunk_size:
            # Paragraph is too large. Attempt to split by sentences
            sentences = para.replace(". ", ".\n").split("\n")
            for sent in sentences:
                sent = sent.strip()
                if not sent:
                    continue
                if len(current_chunk) + len(sent) < chunk_size:
                    current_chunk += (sent + " ")
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = sent + " "
        else:
            if len(current_chunk) + len(para) < chunk_size:
                current_chunk += (para + "\n\n")
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"
                
    if current_chunk:
        chunks.append(current_chunk.strip())
        
    return chunks

class DocumentIngestionPipeline:
    """Manages the lifecycle of RAG documents: reading, parsing, chunking, and vector indexing."""
    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager

    async def ingest_document(self, file_path: Path, custom_source_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Parses text from TXT, PDF, or DOCX, chunks it semantically,
        and indexes the chunks inside ChromaDB.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
            
        source_name = custom_source_name or file_path.name
        logger.info(f"Ingesting file: {source_name} (Size: {file_path.stat().st_size} bytes)")
        
        # 1. Parse text based on suffix
        text = extract_document_content(file_path)
        if not text.strip():
             raise ValueError("Parsed document yielded zero text characters.")
             
        # 2. Chunk text
        chunks = chunk_text(text)
        logger.info(f"Split {source_name} into {len(chunks)} chunks.")
        
        # 3. Save chunks in vector database
        success = self.memory.save_document_chunks(source_name, chunks)
        if not success:
            raise RuntimeError("ChromaDB failed to save document chunks.")
            
        return {
            "source": source_name,
            "chunk_count": len(chunks),
            "total_chars": len(text),
            "timestamp": time.time()
        }
