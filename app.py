import json
import logging

from flask import Flask, request, render_template, send_from_directory, jsonify
from flask_socketio import SocketIO
from PyPDF2 import PdfReader, PdfWriter
import os

from data import ExcelHandler
from llm import extract_invoice
from ocr import pdf_ocr
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

    # anno_result[f"{filename}_{page}"]转json，然后修改key对应的值，再转回来
    anno_json = json.loads(anno_result[f"{filename}_{page}"])
    anno_json[key] = val
    anno = anno_result[f"{filename}_{page}"] = json.dumps(anno_json, ensure_ascii=False, indent=4)

    if clicked:
        excel_handler.update_row(filename, page, ret, anno, key, raw)
    else:
        excel_handler.remove_key_from_down(filename, page, key)

    excel_handler.save_dataframe_to_excel()

    return jsonify({'status': 'success'})


@app.route('/switch_channel', methods=['POST'])
def switch_channel():
    data = request.json
    channel = int(data['channel'])
    app.logger.debug(f"switch_channel: {channel}")

    values = tuple(item.value for item in llm.Channel)
    if channel not in values:
        return jsonify({'status': 'fail', 'msg': f'频道 {channel} 切换失败'})

    llm.switch_channel(channel)
    app.logger.info(f"切换到频道 {llm.Channel(channel)}")
    return jsonify({'status': 'success', 'msg': f'频道 {llm.Channel(channel)} 切换成功'})


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
def process_data_and_emit_progress(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    with open(file_path, 'rb') as file:
        progress = 0

        app.logger.debug(f"正在读取：{filename}...")
        reader = PdfReader(file)
        num_pages = len(reader.pages)

        for page_no in range(1, num_pages + 1):
            page = reader.pages[page_no - 1]
            text = page.extract_text()

            if not text or len(text) < 30:  # 扫描件
                text, progress = ocr(file_path, page, progress, page_no, num_pages)

            progress += 50 * (page_no / num_pages)
            info_progress(progress, f"提取发票要素({page_no}/{num_pages}页)...")
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

    app.logger.debug(f"处理完成")
    info_progress(100, 'done')


# ocr. 先写到一个pdf，在读（待优化）
def ocr(file_path, page, progress, page_no, num_pages):
    writer = PdfWriter()
    writer.add_page(page)

    src_filename = os.path.basename(file_path)
    dest_filename = f"{os.path.splitext(src_filename)[0]}_{page_no}.pdf"
    dest_path = os.path.join(app.config['UPLOAD_FOLDER'], 'tmp', dest_filename)

    with open(dest_path, 'wb') as output_pdf:
        writer.write(output_pdf)

    app.logger.debug(f"准备OCR({page_no}/{num_pages}页):{dest_path}")
    progress += 20 * (page_no / num_pages)
    info_progress(progress, f"正在用OCR提取文本({page_no}/{num_pages}页)...")
    text = pdf_ocr(dest_path)

    return text, progress


@app.route('/uploaded', methods=['GET'])
def uploaded_file():
    filename = request.args.get('filepath')
    app.logger.debug(f"Get: {filename}")
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'


def info_progress(progress, msg):
    socketio.emit('progress', {'progress': progress, 'status': msg})


def info_data(data, page):
    json_data = json.loads(data)
    socketio.emit('data', {'data': json_data, 'page': page})


if __name__ == '__main__':
    socketio.run(app, allow_unsafe_werkzeug=True, port=8000)
