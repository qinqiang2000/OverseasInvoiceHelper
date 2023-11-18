from paddleocr import PaddleOCR
import os


# 初始化一个OCR识别器
ocr = PaddleOCR(use_angle_cls=True, use_gpu=False, page_num=1, show_log=False)


def pdf_ocr(img_path):
    result = ocr.ocr(img_path)

    text_list = []
    for idx in range(len(result)):
        res = result[idx]
        for line in res:
            text_list.append(line[-1][0])

    ret = '\n'.join(text_list)

    return ret
