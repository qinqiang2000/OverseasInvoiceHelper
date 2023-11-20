from paddleocr import PaddleOCR
import os
from docx import Document
import mammoth
import subprocess

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


def direct_docx(file_path):
    doc = Document(file_path)

    text_list = []
    for para in doc.paragraphs:
        text_list.append(para.text)

    for t in doc.tables:
        for r in t.rows:
            row_cnt = [cell.text for cell in r.cells]
            text_list.append(', '.join(row_cnt))

    ret = '\n'.join(text_list)
    print(ret)


# 定义一个忽略图片处理的函数
def ignore(image):
    return {"src": ""}  # 返回一个空的 src 属性，这样图片不会显示


def convert_docx_to_html(file_path):
    with open(file_path, "rb") as docx_file:
        result = mammoth.convert_to_html(docx_file, convert_image=mammoth.images.img_element(ignore))
        html_content = result.value  # 生成的 HTML 内容
        messages = result.messages  # 转换过程中的任何消息
        return html_content


def pdf_structure(path):
    det_folder = os.path.split(path)[0]
    # cmd = f"paddleocr --image_dir={path} --output={det_folder} --type=structure --recovery=true --use_pdf2docx_api=true"
    # print(cmd)
    # os.system(cmd)
    cmd = [
        "paddleocr",
        "--image_dir", path,
        "--output", det_folder,
        "--type", "structure",
        "--recovery", "true",
        "--use_pdf2docx_api", "true"
    ]

    subprocess.run(cmd)

    det_file = os.path.basename(path).split('.')[0] + '.docx'
    det_path = f"{det_folder}/{det_file}"

    return convert_docx_to_html(det_path)