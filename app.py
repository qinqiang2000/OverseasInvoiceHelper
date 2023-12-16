import json
import logging
import os

from dotenv import load_dotenv
from flask import Flask, request, render_template, send_from_directory, jsonify
from flask_socketio import SocketIO

import llm
from data import ExcelHandler
import threading
import queue
from retrieval.doc_loader import async_load


load_dotenv(override=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 限制文件大小为16MB
app.logger.setLevel(logging.DEBUG)

socketio = SocketIO(app)

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# 保存标注数据到excel文件
excel_handler = ExcelHandler('data.xlsx')

# 缓存ocr、llm提取和标注的结果。todo：去掉这一层，直接写持久层
llm_result = {}
ocr_result = {}
anno_result = {}
# a: PyMuPDF(fitz) b: pdfplumber c: pdfminer d: camelot e: tabula
pdf_parser = "b"


class Progress:
    def __init__(self, filename):
        self.id = filename

    def set_progress(self, progress, msg):
        app.logger.info(f"progress: {progress}, msg: {msg}")
        socketio.emit('progress', {'progress': progress, 'status': msg, 'id': self.id})


@app.route('/')
def index():
    return render_template('pdf_viewer.html', filename=None)


# 处理标注的数据（哪一个文件，哪一页的哪个要素key识别不好, 标注的值value是）
@app.route('/down', methods=['POST'])
def handle_icon_click():
    data = request.json
    filename = data['filename']
    page = int(data['page'])  # 从1开始
    key = data['key']
    val = data['value']
    clicked = data['clicked']

    if not f"{filename}_{page}" in llm_result:
        return jsonify({'status': 'error', 'msg': f'{filename}和{page}没有对应的数据'})

    ret = llm_result[f"{filename}_{page}"]
    raw = ocr_result[f"{filename}_{page}"]

    anno_json = json.loads(anno_result[f"{filename}_{page}"])
    anno_json[key] = val
    anno = anno_result[f"{filename}_{page}"] = json.dumps(anno_json, ensure_ascii=False, indent=4)

    if clicked:
        excel_handler.update_row(filename, page, ret, anno, key, raw)
    else:
        excel_handler.remove_key_from_down(filename, page, key)

    excel_handler.save_dataframe_to_excel()

    return jsonify({'status': 'success'})


# 切换llm通道和pdf解析方法，方便平时测试
@app.route('/switch_channel', methods=['POST'])
def switch_channel():
    data = request.json

    # 如果channel是数字，说明是切换llm通道
    if data['channel'].isdigit():
        channel = int(data['channel'])
        values = tuple(item.value for item in llm.Channel)
        if channel not in values:
            return jsonify({'status': 'fail', 'msg': f'频道 {channel} 切换失败'})

        llm.switch_channel(channel)
        app.logger.info(f"切换到频道 {llm.Channel(channel)}")
        return jsonify({'status': 'success', 'msg': f'频道 {llm.Channel(channel)} 切换成功'})
    # 如果channel不是数字，说明是切换pdf解析方法
    else:
        global pdf_parser
        pdf_parser = data['channel']
        app.logger.info(f"切换到pdf解析方法 {pdf_parser}")
        return jsonify({'status': 'success', 'msg': f'切换到pdf解析方法[ {pdf_parser}] 切换成功'})


@app.route('/text', methods=['POST'])
def get_raw_test():
    data = request.json
    filename = data['filename']
    page = data['page']

    if not f"{filename}_{page}" in ocr_result:
        return jsonify({'status': 'error', 'msg': f'{filename}和{page}没有对应的数据'})

    return jsonify({'status': 'success', 'text': ocr_result[f"{filename}_{page}"]})


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        app.logger.debug("没有收到文件")
        return jsonify({'err': "没有收到文件"})

    file = request.files['file']
    if file.filename == '':
        return '没有选择文件'

    if file and allowed_file(file.filename):
        app.logger.debug(f"收到{file.filename}")
        # filename = secure_filename(file.filename)
        filename = file.filename
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(os.path.dirname(file_path)):
            os.makedirs(os.path.dirname(file_path))
        file.save(file_path)

        socketio.start_background_task(process_data_and_emit_progress, filename)
        app.logger.debug(f"保存{file.filename}")

        return jsonify({'filename': filename})
        # return render_template('pdf_viewer.html', filename=filename)


def process_data_and_emit_progress(filename):
    # 创建一个进度条
    pg = Progress(filename)

    # 创建一个队列用于和文档load线程通信
    q = queue.Queue()
    # 异步加载文档
    doc_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    threading.Thread(target=async_load, args=(doc_path, q,)).start()
    page_no = 0
    total = None
    while True:
        if total is None:
            pg.set_progress(1, f"正在识别第{page_no+1}页...")
        else:
            pg.set_progress(int(50*page_no/total), f"正在识别第{page_no+1}页...")

        page_no, text, total = q.get()  # 从队列获取进度和结果, page_no 从1开始
        if page_no == -1:
            break

        # LLM提取要素
        pg.set_progress(int(75*page_no/total), f"正在LL提取第{page_no}页...")
        ret = llm.extract_invoice(text, filename)

        # 完成一次任务，给前端发送进度
        info_data(ret, page_no)

        # 将原始text和ret保存到字典llm_result，key为filename+page_no
        ocr_result[f"{filename}_{page_no}"] = text
        llm_result[f"{filename}_{page_no}"] = anno_result[f"{filename}_{page_no}"] = ret

        # 持久化
        match = excel_handler.match(filename, page_no)
        if not match.empty:
            row_index = match.index[0]
            anno_result[f"{filename}_{page_no}"] = match.at[row_index, 'anno']
            match.at[row_index, 'result'] = ret
            match.at[row_index, 'down'] = []
            match.at[row_index, 'raw'] = text
        else:
            excel_handler.add_row_to_dataframe({'filename': filename, 'page': page_no,
                                                'result': ret, 'anno': ret, 'down': [], 'raw': text})
        excel_handler.save_dataframe_to_excel()

    pg.set_progress(100, "done")


@app.route('/uploaded', methods=['GET'])
def uploaded_file():
    filename = request.args.get('filepath')
    print("uploaded_file: ", app.config['UPLOAD_FOLDER'], filename)
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'pdf'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def info_data(data, page):
    json_data = json.loads(data)
    socketio.emit('data', {'data': json_data, 'page': page})


if __name__ == '__main__':
    socketio.run(app, allow_unsafe_werkzeug=True, host="0.0.0.0", port=8000)
