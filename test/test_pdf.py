import os

import fitz  # PyMuPDF

all_fonts = set()  # 使用集合来避免重复


def list_pdf_fonts(pdf_path):
    doc = fitz.open(pdf_path)

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        for font in page.get_fonts():
            font_name = font[2]  # 可以获取更多字体信息
            all_fonts.add(font_name)

    doc.close()
    return all_fonts


def list_path_fonts(pdf_path):
    # 遍历pdf_path目录下的所有pdf文件
    for root, dirs, files in os.walk(pdf_path):
        for file in files:
            if not file.endswith(".pdf"):
                continue

            file_path = os.path.join(root, file)
            fts = list_pdf_fonts(file_path)
            # if len(fts) > 0:
            #     print(file_path, fonts)

    print(all_fonts)


# list_path_fonts('/Users/qinqiang02/job/test/发票测试数据')

file_path = 'YOSUN 7723072318-7723072381.pdf'
fonts = list_pdf_fonts(file_path)
print(fonts)

import pdfplumber
import hashlib

def calculate_image_hash(image_path):
    # 打开图像文件
    with open(image_path, 'rb') as file:
        image_data = file.read()

    # 创建哈希对象并更新图像数据
    hasher = hashlib.md5()
    hasher.update(image_data)
    return hasher.hexdigest()

def extract_text_and_images(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            # 提取文本
            text = page.extract_text()
            # print(f"Page {page_num + 1} Text:\n{text}\n")

            # 提取图片
            im_list = page.images
            for im_index, im in enumerate(im_list, start=1):
                # 提取图片的边界框
                bbox = (im['x0'], im['top'], im['x1'], im['bottom'])
                cropped_page = page.crop(bbox)

                # 提取并保存图片
                image = cropped_page.to_image()
                image_filename = f"page_{page_num + 1}_img_{im_index}.png"
                image.save(image_filename, format="PNG")
                print(f"Saved image: {image_filename}：hash：{calculate_image_hash(image_filename)}")

extract_text_and_images(file_path)
