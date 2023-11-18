import functools
import json
import threading

import requests
from openai import OpenAI
from dotenv import load_dotenv
from enum import Enum


load_dotenv(override=True)
client = OpenAI()

template = """
根据用户给出的文档内容，提取特定信息并以JSON格式返回。内容可能是发票、装箱单或其他类型。执行以下步骤：
1. 检查文档是否标记为"packing list"、"packing slip"、"装箱单"、"attached-sheet"等，或包含这些词汇。如果是，认定为非发票并返回错误代码和文档类型（例如：{"err": "E0001", 
"msg": /*可能的文档类型*/}）。

2. 如果文档是发票且包含如 'page 1 of 3' 的多页信息，但缺少 "total"、"Amount"、"总金额" 等关键词，返回错误代码和相关页数（例如：{"err": "E0002", "msg": /*第几页*/}）。

3. 提取并记录以下信息：
   - 发票编号（Invoice No.）
   - 发票日期（Invoice Date）
   - 币种（Currency）
   - 总金额（Amount）
   - 收票方（Bill To）
   - 开票方（From）

注意：
   - 确保英文信息中的单词间有正确的空格。
   - "Amount" 应以数字类型提取，如果没有"Amount"，则查找 "Total Amount"。
   - 币种（Currency）应明确标出，例如 'USD'。
   - 如果缺少 "Bill To" 信息，可以查找 'MESSRS'。避免提取包含 'LOGISTICS' 或类似关键词的运输信息（Ship To）。
   - "From" 信息，如果没有直接信息，可以查找 'Account Name' 或 'Beneficiary Name'，如果都没有，提取发票标题中的公司名称。
   - 如果 "Bill To" 或 "From" 包含中英文信息，只提取英文部分，排除地址信息。
   - 检查 "Bill To" 或 "From" ，如果有地址信息，删除它
仅输出JSON结果，不包含其他文字。
"""


class Channel(Enum):
    MOCK = 1
    RPA = 2
    GPT4 = 3


channel = Channel.MOCK
rpa_server_url = 'http://127.0.0.1:9999/api/'
sem_rpa = threading.Semaphore(0)
rpa_result = {}


def switch_channel(new_channel):
    global channel
    channel = Channel(new_channel)


def extract_invoice(text, text_id=""):
    if channel == Channel.MOCK:
        return """ {
          "Invoice No.": "4510044687",
          "Invoice Date": "2023/08/04",
          "Currency": "USD",
          "Amount": 4590.00,
          "Bill To": "HISENSE BROADBAND MULTIMEDIA TECHNOLOGIES (HK) CO., LIMITED",
          "From": "Hisense Broadband Multimedia Technologies(HK) Co., Limited"
        }"""

    elif channel == Channel.RPA:
        return rpa_extract(text, text_id)

    response = client.chat.completions.create(
        model="gpt-4-1106-preview",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": template},
            {"role": "user", "content": text}
        ]
    )

    print("total tokens:", response.usage.total_tokens)
    print(response.choices[0].message.content)

    return response.choices[0].message.content


def rpa_extract(text, reqid):
    prompt = template + "\n用户给的文档内容如下：\n```" + text + "\n```"
    url = rpa_server_url + 'chat'
    data = {'reqid': reqid, 'text': prompt}

    result = requests.post(url, json=data).json()
    if result['status'] == 'fail':
        # 将json错误信息转成字符串，以便在前端显示
        return json.dumps({"error": "fail: 要素提取程序错误"})

    # 调用异步函数，并等待异步函数结束
    schedule_get_request(reqid=reqid)

    success = sem_rpa.acquire(timeout=39)
    if not success:
        return json.dumps({"error": f"等待超时：{reqid}要素提取程序错误"})

    return rpa_result['reqid']


# 定时执行 GET 请求的函数
def schedule_get_request(reqid, interval=2):
    if not send_get_request(reqid):
        # 使用 functools.partial 来传递额外参数
        threading.Timer(interval, functools.partial(schedule_get_request, reqid, interval)).start()


def send_get_request(reqid):
    url = rpa_server_url + 'find'
    params = {'reqid': reqid}
    response = requests.get(url, params=params)
    result = response.json()

    if result.get('data'):
        data = result['data']['data']
        print('Data received:', 'reqid:', result['data']['reqid'], '\n', data)

        rpa_result['reqid'] = data
        sem_rpa.release()
        return True
    else:
        # print('No data yet.')
        return False

