import hashlib
import json
import os
import os.path as osp
import queue
import threading
from functools import wraps

from flask import Flask, request, abort, jsonify, make_response
import logging

from provider import llm
from retrieval.doc_loader import async_load

app = Flask(__name__)

# 用于存储令牌的集合
tokens = set()

upload_folder = osp.join(os.getcwd(), 'uploads')
allowed_extensions = {'jpg', 'jpeg', 'png', 'pdf'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def load_keys():
    """从文件加载令牌到集合中"""
    with open('keys.txt', 'r') as f:
        for line in f:
            tokens.add(line.strip())


def verify_token(token):
    """验证令牌是否有效"""
    return token in tokens


def require_auth(f):
    """认证"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith("Bearer "):
            return std_response(errcode="A0401", description="Authorization header missing or invalid", status_code=401)
            # abort(401, description="Authorization header missing or invalid")

        token = auth_header.split(" ")[1]
        if not verify_token(token):
            return std_response(errcode="A0312", description="Invalid token", status_code=403)

        return f(token, *args, **kwargs)
    return decorated_function


def handle_exceptions(f):
    """统一异常处理"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logging.info(f"Exception: {e}")
            return std_response(errcode="B0001", description=str(e))
    return decorated_function


def std_response(data=None, errcode="0000", description="操作成功", status_code=200):
    response = {
        "errcode": errcode,
        "description": description,
        "data": data
    }
    return make_response(jsonify(response), status_code)


def extract_invoice_content(doc_path):
    """提取发票内容"""
    content = []

    # 异步加载并识别文档，多页文档可以并行
    q = queue.Queue()
    threading.Thread(target=async_load, args=(doc_path, q,)).start()
    while True:
        page_no, text, total = q.get()  # 从队列获取进度和结果, page_no 从1开始
        if page_no == -1:
            break

        # LLM提取要素
        ret = llm.extract_invoice(text, os.path.basename(doc_path))
        content.append(ret)

    json_content = [json.loads(item) for item in content]
    return json_content


# 根据上传的文件，创建并一个发票结构化数据内容对象
@app.route('/v1/invoice/content', methods=['POST'])
@require_auth
@handle_exceptions
def invoice(token):
    if 'file' not in request.files:
        logging.warning("没有收到文件")
        return std_response(None, "A0401", "没有收到文件")

    file = request.files['file']
    if not file or not allowed_file(file.filename):
        logging.warning(f"非法文件:{file.filename}")
        return std_response(None, "A0421", f"非法文件，只能接受：{allowed_extensions}")

    # 计算该文件的hash值
    file_hash = hashlib.md5(file.read()).hexdigest()
    file.seek(0)

    # 重复识别判断
    content_path = osp.join(upload_folder, token, file_hash, f"{osp.splitext(file.filename)[0]}.json")
    if osp.exists(content_path):
        logging.info(f"文件[{file.filename}]已经识别过，直接返回")
        with open(content_path, 'r') as f:
            content = json.load(f)
        return std_response(content)

    # 暂存文件
    file_path = osp.join(upload_folder, token, file_hash, file.filename)
    os.makedirs(osp.dirname(file_path), exist_ok=True)
    file.save(file_path)
    logging.info(f"收到{file.filename}: {file_hash}")

    # 提取内容
    content = extract_invoice_content(file_path)

    # 将content保存到json文件中
    with open(content_path, 'w') as f:
        json.dump(content, f, ensure_ascii=False, indent=4)

    logging.info(f"[{token}]的[{file.filename}]提取到发票内容: {content}")

    return std_response(content)


# 从文件加载令牌。需要在服务器启动之前调用
load_keys()

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=80)
