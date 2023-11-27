from paddleocr import PaddleOCR

paddle_ocr = PaddleOCR(use_gpu=True, cpu_threads=8)


def pdf_ocr(img_path):
    global paddle_ocr
    result = paddle_ocr.ocr(img_path)

    text_list = []
    for idx in range(len(result)):
        res = result[idx]
        for line in res:
            text_list.append(line[-1][0])

    ret = '\n'.join(text_list)

    return ret


path = "../uploads/2.pdf"

text = pdf_ocr(path)
print(text)
