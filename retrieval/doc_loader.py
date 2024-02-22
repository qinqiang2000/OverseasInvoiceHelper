import os
import os.path as osp
import pdfplumber
from dotenv import load_dotenv
import logging
from retrieval.ocr import ocr

logging.basicConfig(format='[%(asctime)s %(filename)s:%(lineno)d] %(levelname)s: %(message)s', level=logging.INFO, force=True)
load_dotenv(override=True)
fonts_list = os.getenv("KNOWN_FONTS").split(',')


# 异步读取文档，将结果放入队列
# 队列元素是一个三元组：(页码, 识别结果, 总页数)； 页码为-1表示结束
def async_load(doc_path, queue):
    # 非pdf文件，直接ocr
    if not doc_path.lower().endswith(".pdf"):
        logging.info(f"put to queue: {osp.split(doc_path)[1]}")
        queue.put((1, ocr(doc_path, -1), 1))
        queue.put((-1, None, -1))
        return

    pdf = pdfplumber.open(doc_path)
    num_pages = len(pdf.pages)
    for page in pdf.pages:
        text = page.extract_text()

        # todo: 校验字体
        if not text or len(text) < 39 or len(page.images) > 5:  # 扫描件，39是一个经验值
            logging.info(f"扫描件[{osp.split(doc_path)[1]}]: len(text)[{len(text)}], len(images)[{len(page.images)}]")
            text = ocr(doc_path, page.page_number)

        logging.info(f"[{osp.split(doc_path)[1]}] put to queue: {page.page_number}")
        queue.put((page.page_number, text, num_pages))

    logging.info(f"[{osp.split(doc_path)[1]}] put to queue: finish")
    queue.put((-1, None, -1))


# pdfplumber的文本更全一点
def extract_text(pdf_path, page_no=0, parser='b'):
    pdf = pdfplumber.open(pdf_path)
    page = pdf.pages[page_no]
    return page.extract_text()


def known_fonts(font):
    return font in fonts_list
