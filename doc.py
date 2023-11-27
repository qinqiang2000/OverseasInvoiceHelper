import pdfplumber


def extract_text(pdf_path, page_no=0, parser='b'):
    pdf = pdfplumber.open(pdf_path)
    page = pdf.pages[page_no]
    return page.extract_text()