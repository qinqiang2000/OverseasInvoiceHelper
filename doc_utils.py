import os
import pdfplumber
from dotenv import load_dotenv

load_dotenv(override=True)
fonts_list = os.getenv("KNOWN_FONTS").split(',')


# pdfplumber的文本更全一点
def extract_text(pdf_path, page_no=0, parser='b'):
    pdf = pdfplumber.open(pdf_path)
    page = pdf.pages[page_no]
    return page.extract_text()


def known_fonts(font):
    return font in fonts_list
