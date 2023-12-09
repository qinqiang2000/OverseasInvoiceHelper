import os
import pdfplumber
from dotenv import load_dotenv
import logging
from retrieval.ocr import ocr

logging.basicConfig(format='[%(asctime)s %(filename)s:%(lineno)d] %(levelname)s: %(message)s', level=logging.INFO, force=True)
load_dotenv(override=True)
fonts_list = os.getenv("KNOWN_FONTS").split(',')


def async_load(doc_path, queue):
    pdf = pdfplumber.open(doc_path)
    num_pages = len(pdf.pages)
    for page in pdf.pages:
        text = page.extract_text()

        # todo: 校验字体
        if not text or len(text) < 39:  # 扫描件，39是一个经验值
            text = ocr(doc_path, page.page_number)

        logging.info(f"=========put to queue: {page.page_number}==========")
        queue.put((page.page_number, text, num_pages))

    queue.put((-1, None, -1))


# pdfplumber的文本更全一点
def extract_text(pdf_path, page_no=0, parser='b'):
    pdf = pdfplumber.open(pdf_path)
    page = pdf.pages[page_no]
    return page.extract_text()


def known_fonts(font):
    return font in fonts_list
