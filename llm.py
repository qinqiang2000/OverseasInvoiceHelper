import functools
import json
import re
import threading

import requests
from openai import OpenAI
from dotenv import load_dotenv
from enum import Enum
from opencc import OpenCC

load_dotenv(override=True)
client = OpenAI()
packing_keywords = ["packing list", "packing slip", "装箱单",
                    "attached-sheet", "WEIGHT MEMO", "清单明细", '清單明', "装箱明细", "装箱", "CONTENT LIST"]
express_keywords = ["waybill", "way bill", "express worldwide", "Delivery Note", "Delivery No", "收单"]
logistics_keywords = ["LOGISTICS", "物流", "快递"]
invoice_keywords = ["COMMERCIAL INVOICE", "Invoice Date", "Invoice No", "Invoice Number"]


def init_keywords(keywords_list):
    for keywords in keywords_list:
        cc = OpenCC('s2t')  # s2t 表示从简体到繁体
        # 对列表中的每个简体中文词汇进行转换，并添加到原列表中
        for word in list(keywords):  # 使用 list(keywords) 创建原列表的副本以进行迭代
            try:
                traditional_word = cc.convert(word)
                if traditional_word != word:  # 只有当转换后的词与原词不同时才添加
                    keywords.append(traditional_word)
            except Exception as e:
                print(f"转换时出错: {e}")

        # 对keywords里面的空格用'_'替换后，加入到keywords中
        for word in list(keywords):
            if ' ' in word:
                keywords.append(word.replace(' ', '_'))
        print(keywords)


init_keywords([packing_keywords, express_keywords, logistics_keywords, invoice_keywords])

template = """
根据用户给出的内容，识别出文档类型，提取特定信息并以JSON格式返回。执行以下步骤：
1.  提取并记录以下信息：
   - 文档类型（Doc Type） 只有Invoice或其他
   - 发票编号（Invoice No.）
   - 发票日期（Invoice Date）
   - 币种（Currency）
   - 总金额（Amount）
   - 收票方（Bill To）
   - 开票方（From）
   - Ship To

注意：
   - 确保英文信息中的单词间有正确的空格
   - 如果找不到对应信息，则json的值置为空
   - "Invoice No." 如果没有"Invoice No."，则查找 "Invoice Number"。
   - "Amount" 应以数字类型提取，如果没有"Amount"，则查找 "Total Amount"或者"Total Value"。
   - 币种（Currency）应明确标出，例如 'USD'。
   - 如果缺少 "Bill To" 信息，可以查找 'MESSRS'
   - 如果"Bill To"提取到包含 'LOGISTICS' 或类似的物流公司信息，将""Bill To"和"Ship To"的值调换
   - "From" 信息，如果没有直接信息，可以查找 'Account Name' 或 'Beneficiary Name'，如果都没有，提取发票标题中的公司名称。
   - 检查 "Bill To" 或 "From" ，如果有地址信息，删除它
   - 检查 "Bill To" 或 "From" ，如果没正确分词，对他们进行分词

2. 如果文档是发票且包含如 'page 1 of 3' 的多页信息，增加一个page的字段，值为：第几页/页数
3. 仅输出JSON结果，不包含其他文字。
"""


class Channel(Enum):
    MOCK = 1
    RPA = 2
    GPT4 = 3
    GPT35 = 4


channel = Channel.GPT4
rpa_server_url = 'http://127.0.0.1:9999/api/'
sem_rpa = threading.Semaphore(0)
rpa_result = {}


def switch_channel(new_channel):
    global channel
    channel = Channel(new_channel)


def post_process(result):
    ret = json.loads(result)

    # 删除多余的字段：Ship To
    ship_to = ret.get("Ship To")
    bill_to = ret.get("Bill To")
    # 如果ship包含物流关键词，则删除
    if bill_to and contain_keywords(bill_to, logistics_keywords) and ship_to:
        print(f"bill to 包含物流关键词：{bill_to}, 和{ship_to}替换")
        ret["Ship To"] = bill_to
        ret["Bill To"] = ship_to

    if "Ship To" in ret:
        ret.pop("Ship To")

    return json.dumps(ret)


def pre_process(text):
    # 如果是packing list的，则直接返回
    if contain_keywords(text, packing_keywords):
        return json.dumps({"Doc Type": "非发票：可能是装货单、waybill或其他",
                           "Invoice No.": "", "Invoice Date": "", "Currency": "", "Amount": None,
                           "Bill To": "", "From": ""})

    # 如果是waybill或express的，则再检查一次不是发票，才返回
    if contain_keywords(text, express_keywords):
        if not contain_keywords(text, invoice_keywords):
            return json.dumps({"Doc Type": "非发票：可能是装货单、waybill或其他",
                               "Invoice No.": "", "Invoice Date": "", "Currency": "", "Amount": None,
                               "Bill To": "", "From": ""})

    return None


# 入口，包括事前、事中、事后处理
def extract_invoice(text, text_id=""):
    # 事前
    ret = pre_process(text)
    if ret:
        return ret

    # 事中
    ret = extract(text, text_id)

    # 事后
    return post_process(ret)


def extract(text, text_id=""):
    if channel == Channel.MOCK:
        return """ {
        "Doc Type": "Invoice",
          "Invoice No.": "4510044687",
          "Invoice Date": "2023/08/04",
          "Currency": "USD",
          "Amount": 4590.00,
          "Bill To": "HISENSE BROADBAND MULTIMEDIA TECHNOLOGIES (HK) CO., LIMITED",
          "From": "Hisense Broadband Multimedia Technologies(HK) Co., Limited"
        }"""

    elif channel == Channel.RPA:
        return rpa_extract(text, text_id)

    model = "gpt-3.5-turbo-1106"
    if channel == channel.GPT4:
        model = "gpt-4-1106-preview"

    print("使用模型API：", model, text_id)
    response = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": template},
            {"role": "user", "content": text}
        ]
    )

    print("total tokens:", response.usage.total_tokens)
    print(response.choices[0].message.content)

    return response.choices[0].message.content


def contain_keywords(text, excludes):
    # 将关键词列表转换为正则表达式
    # 使用 \s* 来匹配关键词中可能存在的空格或换行符
    keywords_pattern = '|'.join([keyword.replace(" ", r"\s*") for keyword in excludes])
    pattern = re.compile(keywords_pattern, re.IGNORECASE)

    return bool(pattern.search(text))


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

    success = sem_rpa.acquire(timeout=69)
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

# text_to_check = """
# """
# if should_exclude(text_to_check):
#     print("文本包含关键词")
# else:
#     print("文本不包含关键词")
