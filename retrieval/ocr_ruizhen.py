import mimetypes
import os

import requests
import hashlib
import time


app_key = "s60gby076vd6qqgd"
secret = os.environ.get("RUIZHEN_APP_SECRET")
language = os.environ.get("RUIZHEN_OCR_LANG", "eng")
url = "https://api.regenai.com/v1/general/fetch"


def generate_token(app_key, secret):
    """Generate the token using md5 hashing."""
    timestamp = str(int(time.time()))
    token_string = f"{app_key}+{timestamp}+{secret}"
    token = hashlib.md5(token_string.encode(encoding='UTF-8')).hexdigest()
    return token, timestamp


def extract_text(ret):
    if ret['result'] != 1:
        return "请求失败"

    text_list = []
    results = ret['response']['data']['identify_results']
    for result in results:
        for p in result['details']['print']:
            text_list.append(p['result'])
        for h in result['details']['handwritten']:
            text_list.append(h['result'])

    return "\n".join(text_list)


def ruizhen_ocr(img_path):
    mime_type, _ = mimetypes.guess_type(img_path)
    if mime_type is None:
        mime_type = 'application/octet-stream'  # 使用默认的MIME类型
    with open(img_path, 'rb') as file:
        files = {'image_file': (img_path, file, mime_type)}  # 'file' 是字段名，根据API具体要求可能需要更改
        token, timestamp = generate_token(app_key, secret)

        data = {
            'app_key': app_key,
            'token': token,
            "timestamp": timestamp,
            'language': language,
        }

        # 发送POST请求
        response = requests.post(url, files=files, data=data)

        return extract_text(response.json())
