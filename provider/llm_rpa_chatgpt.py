import json
import logging
import threading
import functools
import requests

rpa_server_url = 'http://127.0.0.1:9999/api/'


class ChatGPTRPA:
    def __init__(self):
        self.sem_rpa = threading.Semaphore(0)
        self.rpa_result = {}

    # 定时执行 GET 请求的函数
    def schedule_get_request(self, reqid, interval=2):
        if not self.send_get_request(reqid):
            # 使用 functools.partial 来传递额外参数
            threading.Timer(interval, functools.partial(self.schedule_get_request, reqid, interval)).start()

    def send_get_request(self, reqid):
        url = rpa_server_url + 'find'
        params = {'reqid': reqid}
        response = requests.get(url, params=params)
        result = response.json()

        if result.get('data'):
            data = result['data']['data']
            print('Data received:', 'reqid:', result['data']['reqid'], '\n', data)

            self.rpa_result['reqid'] = data
            self.sem_rpa.release()
            return True
        else:
            # print('No data yet.')
            return False

    def generate_text(self, text, sys_prompt, reqid):
        prompt = sys_prompt + "\n用户给的文档内容如下：\n```" + text + "\n```"
        url = rpa_server_url + 'chat'
        data = {'reqid': reqid, 'text': prompt}

        try:
            result = requests.post(url, json=data).json()
        except Exception as e:
            logging.error(f"调用RPA出错：{e}")
            return json.dumps({"error": "fail: 调用RPA出错"})

        if result['status'] == 'fail':
            # 将json错误信息转成字符串，以便在前端显示
            return json.dumps({"error": "fail: 要素提取程序错误"})

        # 调用异步函数，并等待异步函数结束
        self.schedule_get_request(reqid=reqid)

        success = self.sem_rpa.acquire(timeout=69)
        if not success:
            return json.dumps({"error": f"等待超时：{reqid}要素提取程序错误"})

        return self.rpa_result['reqid']


