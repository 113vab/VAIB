import logging
from pathlib import Path
import pypdf
import docx

logger = logging.getLogger("vaib")

def extract_text_from_pdf(file_path: Path) -> str:
    """Extract text from a PDF file using pypdf."""
    try:
        reader = pypdf.PdfReader(str(file_path))
        text_parts = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n".join(text_parts)
    except Exception as e:
        logger.error(f"Error parsing PDF {file_path.name}: {e}")
        raise ValueError(f"Failed to parse PDF: {str(e)}")

def extract_text_from_docx(file_path: Path) -> str:
    """Extract text from a Word document (.docx) using python-docx."""
    try:
        doc = docx.Document(str(file_path))
        text_parts = []
        for paragraph in doc.paragraphs:
            if paragraph.text:
                text_parts.append(paragraph.text)
        return "\n".join(text_parts)
    except Exception as e:
        logger.error(f"Error parsing DOCX {file_path.name}: {e}")
        raise ValueError(f"Failed to parse DOCX: {str(e)}")

def extract_text_from_txt(file_path: Path) -> str:
    """Extract text from a UTF-8 text file."""
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            # Fallback to cp1252 / latin-1 if UTF-8 fails
            return file_path.read_text(encoding="latin-1")
        except Exception as e:
            logger.error(f"Error parsing TXT {file_path.name}: {e}")
            raise ValueError(f"Failed to read text file encoding: {str(e)}")
    except Exception as e:
        logger.error(f"Error parsing TXT {file_path.name}: {e}")
        raise ValueError(f"Failed to parse TXT: {str(e)}")

def extract_document_content(file_path: Path) -> str:
    """Extract all text contents automatically based on file extension."""
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
        
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(file_path)
    elif suffix == ".docx":
        return extract_text_from_docx(file_path)
    elif suffix == ".txt":
        return extract_text_from_txt(file_path)
    else:
        raise ValueError(f"Unsupported file format: {suffix}")
