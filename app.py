import json
import logging

from flask import Flask, request, render_template, send_from_directory, jsonify
from flask_socketio import SocketIO
import fitz
import os

from data import ExcelHandler
from doc import extract_text
from llm import extract_invoice
from ocr import ocr
import llm

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
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
    def __init__(self, num_pages=1):
        self.page = 1
        self.num_pages = num_pages

    def set_page(self, page):
        self.page = page

    def set_progress(self, progress, msg, ):
        msg = msg + f"(Page {self.page}/{self.num_pages})"
        app.logger.info(f"progress: {progress}, msg: {msg}")
        socketio.emit('progress', {'progress': progress, 'status': msg})


@app.route('/')
def index():
    return render_template('pdf_viewer.html', filename=None)


# 处理标注的数据（哪一个文件，哪一页的哪个要素key识别不好, 标注的值value是）
@app.route('/down', methods=['POST'])
def handle_icon_click():
    data = request.json
    filename = data['filename']
    page = int(data['page'])
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


# 总体处理上传的文件：
# 1）提取文本
# 2）ocr（如果是图片）
# 3）提取发票要素
# todo：将这个函数拆分成多个函数，放到独立的document_loader模块
def process_data_and_emit_progress(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    with open(file_path, 'rb') as file:
        app.logger.debug(f"正在读取：{filename}...")
        doc = fitz.open(file)
        num_pages = len(doc)
        pg = Progress(num_pages)

        for page_no in range(1, num_pages + 1):
            pg.set_page(page_no)

            page = doc.load_page(page_no-1)
            text = page.get_text("text")

            if not text or len(text) < 39:  # 扫描件，39是一个经验值
                pg.set_progress(20, "正在OCR...")
                text = ocr(app.config['UPLOAD_FOLDER'], filename, doc, page_no)
            elif pdf_parser != 'a':   # 使用其他ocr引擎做提取text
                text = extract_text(file_path, page_no-1, pdf_parser)

            pg.set_progress(60, "正在提取关键信息...")
            ret = extract_invoice(text, filename)

            # 将原始text和ret保存到字典llm_result，key为filename+page_no
            ocr_result[f"{filename}_{page_no}"] = text
            llm_result[f"{filename}_{page_no}"] = anno_result[f"{filename}_{page_no}"] = ret

            # 持久化
            match = excel_handler.match(filename, page_no)
            if not match.empty:
                row_index = match.index[0]
                anno_result[f"{filename}_{page}"] = match.at[row_index, 'anno']
                match.at[row_index, 'result'] = ret
                match.at[row_index, 'down'] = []
                match.at[row_index, 'raw'] = text
            else:
                excel_handler.add_row_to_dataframe({'filename': filename, 'page': page_no,
                                                    'result': ret, 'anno': ret, 'down': [], 'raw': text})
            excel_handler.save_dataframe_to_excel()

            info_data(ret, page_no)

    pg.set_progress(100, "done")


@app.route('/uploaded', methods=['GET'])
def uploaded_file():
    filename = request.args.get('filepath')
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'


def info_data(data, page):
    json_data = json.loads(data)
    socketio.emit('data', {'data': json_data, 'page': page})


if __name__ == '__main__':
    socketio.run(app, allow_unsafe_werkzeug=True, port=8000)
    # process_data_and_emit_progress('II-VI Laser Enterprise GmbH/II-VI SKR230627.pdf')
