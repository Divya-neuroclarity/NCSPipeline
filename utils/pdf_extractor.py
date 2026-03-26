import pdfplumber

def extract_text_from_pdf(pdf_file):
    """
    Extracts raw text from a PDF file using pdfplumber.
    pdf_file can be a path or a file-like object (from Streamlit uploader).
    """
    text = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()
