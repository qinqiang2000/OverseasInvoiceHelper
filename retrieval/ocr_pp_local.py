import os

import fitz
import requests
import logging

ocr_vendor = os.environ.get("OCR_VENDOR")
USE_GPU = os.environ.get("PPOCR_USE_GPU") == "True"

angle_cls_url = 'https://api-sit.piaozone.com/nlp_service/match/file'


# 初始化一PaddleOCR,todo: 这里为省去启动时间，后续要考虑并发
if ocr_vendor == 'ppocr':
    from paddleocr import PaddleOCR
    paddle_ocr = PaddleOCR(use_angle_cls=True, use_gpu=USE_GPU, cpu_threads=8)


def pp_ocr(img_path):
    global paddle_ocr

    up_image(img_path)

    result = paddle_ocr.ocr(img_path)

    text_list = []
    for idx in range(len(result)):
        res = result[idx]
        for line in res:
            text_list.append(line[-1][0])

    ret = '\n'.join(text_list)

    return ret


# 使pdf图片摆正
def up_image(pdf_path):
    with open(pdf_path, 'rb') as file:
        pdf_document = fitz.open(file)

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