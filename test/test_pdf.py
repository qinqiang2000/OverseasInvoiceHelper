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


pdf_path = '/Users/qinqiang02/job/test/发票测试数据'

# 遍历pdf_path目录下的所有pdf文件
for root, dirs, files in os.walk(pdf_path):
    for file in files:
        if not file.endswith(".pdf"):
            continue

        file_path = os.path.join(root, file)
        fts = list_pdf_fonts(file_path)
        # if len(fts) > 0:
        #     print(file_path, fonts)

file_path = '../uploads/世强发票4.pdf'
# fonts = list_pdf_fonts(file_path)
print(all_fonts)