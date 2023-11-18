import json
import logging
import time

from flask import Flask, request, render_template, send_from_directory, jsonify
from flask_socketio import SocketIO
from PyPDF2 import PdfReader, PdfWriter
import os

from llm import extract_invoice
from ocr import pdf_ocr

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 限制文件大小为16MB
app.logger.setLevel(logging.DEBUG)

socketio = SocketIO(app)

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])


@app.route('/')
def index():
    return render_template('pdf_viewer.html', filename=None)


@app.route('/test')
def test():
    return render_template('test.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    app.logger.debug("upload_file___")

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
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        socketio.start_background_task(process_data_and_emit_progress, filename)
        app.logger.debug(f"保存{file.filename}")

        return jsonify({'filename': filename})
        # return render_template('pdf_viewer.html', filename=filename)


def process_data_and_emit_progress(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    with open(file_path, 'rb') as file:
        progress = 0

        app.logger.debug(f"正在读取{filename}...")
        reader = PdfReader(file)
        num_pages = len(reader.pages)

        for i in range(num_pages):
            page_no = i + 1
            page = reader.pages[i]
            text = page.extract_text()

            if text:
                progress += 50 * (page_no / num_pages)
                info_progress(progress, f"提取发票要素({page_no}/{num_pages}页)...")
                socketio.sleep(2)  # 模拟耗时操作
                info_data(extract_invoice(text, filename), page_no)
                continue

            # todo: page直接传给oc
            app.logger.debug(f"正在用OCR提取文本({page_no}/{num_pages})...")
            progress += 20 * (page_no / num_pages)
            info_progress(progress, f"正在用OCR提取文本({page_no}/{num_pages}页)...")
            writer = PdfWriter()
            writer.add_page(page)

            src_filename = os.path.basename(file_path)
            dest_filename = f"{os.path.splitext(src_filename)[0]}_{i + 1}.pdf"
            dest_path = os.path.join(app.config['UPLOAD_FOLDER'], 'tmp', dest_filename)

            with open(dest_path, 'wb') as output_pdf:
                writer.write(output_pdf)

            app.logger.debug(f"准备OCR({page_no}/{num_pages}页):{dest_path}")
            text = pdf_ocr(dest_path)
            print(f"======OCR=======\n{text}")
            progress += 50 * (page_no / num_pages)
            info_progress(progress, f"提取发票要素({page_no}/{num_pages}页)...")
            socketio.sleep(2)  # 模拟耗时操作
            info_data(extract_invoice(text, filename), page_no)

    app.logger.debug(f"处理完成")
    info_progress(100, '处理完成')


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'


def info_progress(progress, msg):
    socketio.emit('progress', {'progress': progress, 'status': msg})


def info_data(data, page):
    json_data = json.loads(data)
    socketio.emit('data', {'data': json_data, 'page': page})


if __name__ == '__main__':
    socketio.run(app, allow_unsafe_werkzeug=True, port=8000, debug=True)
