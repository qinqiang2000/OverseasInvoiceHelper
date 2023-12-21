import logging
import os

import fitz
import requests

from retrieval.ruizhen_ocr import ruizhen_ocr

logging.basicConfig(format='[%(asctime)s %(filename)s:%(lineno)d] %(levelname)s: %(message)s', level=logging.INFO, force=True)

angle_cls_url = 'https://api-sit.piaozone.com/nlp_service/match/file'

ocr_vendor = os.environ.get("OCR_VENDOR")
USE_GPU = os.environ.get("PPOCR_USE_GPU") == "True"

# 初始化一PaddleOCR,todo: 这里为省去启动时间，后续要考虑并发
if ocr_vendor == 'ppocr':
    from paddleocr import PaddleOCR
    paddle_ocr = PaddleOCR(use_angle_cls=True, use_gpu=USE_GPU, cpu_threads=8)


# 使pdf图片摆正
def up_image(pdf_path, pdf_document):
    files = {'file': open(pdf_path, 'rb')}
    # 通过http api识别角度
    response = requests.post(angle_cls_url, files=files)
    files['file'].close()

    response_data = response.json()
    if response_data['errcode'] != "0000":
        return

    # 读取 angle 的值
    angle = int(response_data['data']['angle'])
    logging.info(f"图像{pdf_path}倾斜度是:  {angle}")
    if angle < 30 or angle > 330:
        return

    # 默认只有一页
    pdf_document[0].set_rotation(360 - angle)
    pdf_document.save(pdf_path)
    logging.info(f"已摆正图像右旋转[{360 - angle}]度")


def before_ocr(doc_path, page_no):
    # 将doc_path分成路径和文件名
    with open(doc_path, 'rb') as file:
        doc = fitz.open(file)

    file_path, filename = os.path.split(doc_path)
    file_base, file_extension = os.path.splitext(filename)
    dest_filename = f"{file_base}_{page_no}{file_extension}"
    dest_path = os.path.join(file_path, 'tmp', dest_filename)
    if not os.path.exists(os.path.dirname(dest_path)):
        os.makedirs(os.path.dirname(dest_path))

    # 单独提取第page_no页
    new_doc = fitz.open()
    new_doc.insert_pdf(doc, from_page=page_no-1, to_page=page_no-1)
    new_doc.save(dest_path)
    logging.info(f"已保存第{page_no}页到：{dest_path}")

    # 使pdf图片摆正
    if ocr_vendor == 'ppocr':
        up_image(dest_path, new_doc)

    new_doc.close()
    return dest_path


# todo: ocr. 先写到一个pdf，再读(待优化）
def ocr(doc_path, page_no):
    # 预处理
    dest_path = before_ocr(doc_path, page_no)

    if ocr_vendor == 'ppocr':
        text = pp_ocr(dest_path)
    else:
        text = ruizhen_ocr(dest_path)

    logging.debug(f"[{doc_path}] ocr result:\n {text}]")
    return text


def ocr_img(doc_path):
    # 预处理
    # if ocr_vendor == 'ppocr':
    #     up_image(dest_path, new_doc)

    if ocr_vendor == 'ppocr':
        text = pp_ocr(doc_path)
    else:
        text = ruizhen_ocr(doc_path)

    logging.debug(f"[{doc_path}] ocr result:\n {text}]")
    return text


def pp_ocr(img_path):
    global paddle_ocr
    result = paddle_ocr.ocr(img_path)

    text_list = []
    for idx in range(len(result)):
        res = result[idx]
        for line in res:
            text_list.append(line[-1][0])

    ret = '\n'.join(text_list)

    return ret


