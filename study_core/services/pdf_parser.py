import os
from typing import Union
from pathlib import Path


def extract_text_from_pdf(pdf_path: Union[str, Path]) -> str:
    """
    Extracts text content from a PDF file using pypdf, pdfplumber, or PyPDF2.
    
    :param pdf_path: Absolute or relative file path to the PDF.
    :return: Cleaned text string extracted from the document.
    """
    pdf_path_str = str(pdf_path)
    if not os.path.exists(pdf_path_str):
        raise FileNotFoundError(f"PDF file not found at path: {pdf_path_str}")

    extracted_text = ""

    # Attempt 1: pypdf
    try:
        import pypdf
        reader = pypdf.PdfReader(pdf_path_str)
        pages_text = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                pages_text.append(text)
        extracted_text = "\n\n".join(pages_text)
        if extracted_text.strip():
            return _clean_text(extracted_text)
    except ImportError:
        pass
    except Exception as e:
        print(f"[pypdf extraction warning]: {e}")

    # Attempt 2: pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path_str) as pdf:
            pages_text = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)
            extracted_text = "\n\n".join(pages_text)
            if extracted_text.strip():
                return _clean_text(extracted_text)
    except ImportError:
        pass
    except Exception as e:
        print(f"[pdfplumber extraction warning]: {e}")

    # Attempt 3: PyPDF2 fallback
    try:
        import PyPDF2
        with open(pdf_path_str, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            pages_text = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)
            extracted_text = "\n\n".join(pages_text)
            if extracted_text.strip():
                return _clean_text(extracted_text)
    except ImportError:
        pass
    except Exception as e:
        print(f"[PyPDF2 extraction warning]: {e}")

    if not extracted_text.strip():
        raise ValueError(
            "Could not extract readable text from PDF. "
            "Please ensure a PDF library (pypdf, pdfplumber, or PyPDF2) is installed and the PDF contains selectable text."
        )

    return _clean_text(extracted_text)


def _clean_text(text: str) -> str:
    """Utility to clean up extra whitespace and non-printable characters."""
    lines = [line.strip() for line in text.splitlines()]
    non_empty_lines = [line for line in lines if line]
    return "\n".join(non_empty_lines)
