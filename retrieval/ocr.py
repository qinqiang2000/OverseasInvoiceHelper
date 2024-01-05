import logging
import os

import fitz

from retrieval.ocr_pp_local import pp_ocr
from retrieval.ocr_ruizhen import ruizhen_ocr

logging.basicConfig(format='[%(asctime)s %(filename)s:%(lineno)d] %(levelname)s: %(message)s', level=logging.INFO, force=True)
ocr_vendor = os.environ.get("OCR_VENDOR")


# todo: 先将page_no页写到一个单独pdf，再读(待优化）
def before_ocr(doc_path, page_no):
    # 将doc_path分成路径和文件名
    with open(doc_path, 'rb') as file:
        doc = fitz.open(file)

    file_path, filename = os.path.split(doc_path)
    file_base, file_extension = os.path.splitext(filename)
    dest_path = os.path.join(file_path, 'tmp', f"{file_base}_{page_no}{file_extension}")
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    # 单独提取第page_no页
    new_doc = fitz.open()
    new_doc.insert_pdf(doc, from_page=page_no-1, to_page=page_no-1)
    new_doc.save(dest_path)
    logging.info(f"已保存第{page_no}页到：{dest_path}")

    new_doc.close()
    return dest_path


def ocr(doc_path, page_no):
    # page_no >= 0表示是pdf，需预处理
    if page_no >= 0:
        doc_path = before_ocr(doc_path, page_no)

    if ocr_vendor == 'ppocr':
        text = pp_ocr(doc_path)
    else:
        text = ruizhen_ocr(doc_path)

    logging.debug(f"[{doc_path}] ocr result:\n {text}]")
    return text



