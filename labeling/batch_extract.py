import os
import queue
import threading

from dotenv import load_dotenv

from provider import llm
from labeling.data import ExcelHandler
from retrieval.doc_loader import async_load

load_dotenv(override=True)


def process_data_and_emit_progress(doc_path, excel_handler):
    # 获取文件名
    filename = os.path.basename(doc_path)

    # 创建一个队列用于和文档load线程通信
    q = queue.Queue()

    # 异步加载文档
    threading.Thread(target=async_load, args=(doc_path, q,)).start()
    page_no = 0
    total = None
    while True:
        if total is None:
            print(f"正在识别第{page_no + 1}页...")
        else:
            print(f"正在识别第{page_no + 1}页...")

        page_no, text, total = q.get()  # 从队列获取进度和结果, page_no 从1开始
        if page_no == -1:
            break

        # LLM提取要素
        print(f"正在LLM提取第{page_no}页...")
        ret = llm.extract_invoice(text, filename)

        # 持久化
        excel_handler.add_row_to_dataframe({'filename': filename, 'page': page_no,
                                            'result': ret, 'anno': ret, 'down': [], 'raw': text})
        excel_handler.save_dataframe_to_excel()

    print(f"已经处理完：{filename}")


if __name__ == '__main__':
    folder = "/Users/qinqiang02/job/test/发票测试数据/海外形式发票/海信宽带供应商识别分类_70模板/Yosun Hong Kong Corporation Limited"
    excel_handler = ExcelHandler(os.path.join(folder, 'data.xlsx'))

    # 遍历文件夹，处理每个pdf、png、jpg和jpeg文件
    for root, dirs, files in os.walk(folder):
        for file in files:
            if file.lower().endswith(".pdf") or file.lower().endswith(".png") or file.lower().endswith(
                    ".jpg") or file.lower().endswith(".jpeg"):
                process_data_and_emit_progress(os.path.join(root, file), excel_handler)
