import functools
import json
import logging
import re
import threading

import requests
from openai import OpenAI
from dotenv import load_dotenv
from enum import Enum
from opencc import OpenCC

load_dotenv(override=True)
client = OpenAI()
packing_keywords = {"packing list", "packing slip", "Shipment Packlist", "装箱单", "Delivery Order", "送货单",
                    "attached-sheet", "WEIGHT MEMO", "清单明细", '清單明', "装箱明细", "装箱", "CONTENT LIST"}
express_keywords = {"waybill", "way bill", "express world", "Delivery Note", "Delivery No", "收单",
                    "Certificate of Compliance", "FedEx.", "FedEx。"}
logistics_keywords = {"LOGISTICS", "物流", "快递"}
invoice_keywords = {"COMMERCIAL INVOICE", "Invoice Date", "INV.DATE", "Invoice No", "INV.NO", "Invoice Number"}
invoice_packing_keywords1 = {"INVOICE & PACKING"}
invoice_packing_keywords2 = {"Amount"}


def init_keywords(keywords_list):
    for keywords in keywords_list:
        # 对keywords里面的符号用全角转换后，加入到keywords中
        for word in list(keywords):
            full_width_keyword = ''.join(
                chr(0xFEE0 + ord(c)) if 0x21 <= ord(c) <= 0x7E and not c.isalnum() else c for c in word)
            keywords.add(full_width_keyword)

        cc = OpenCC('s2t')  # s2t 表示从简体到繁体
        # 对列表中的每个简体中文词汇进行转换，并添加到原列表中
        for word in list(keywords):  # 使用 list(keywords) 创建原列表的副本以进行迭代
            try:
                traditional_word = cc.convert(word)
                if traditional_word != word:  # 只有当转换后的词与原词不同时才添加
                    keywords.add(traditional_word)
            except Exception as e:
                print(f"转换时出错: {e}")

        # 对keywords里面的空格用'_'替换后，加入到keywords中
        for word in list(keywords):
            if ' ' in word:
                keywords.add(word.replace(' ', '_'))

        print(keywords)


init_keywords([packing_keywords, express_keywords, logistics_keywords, invoice_keywords,
               invoice_packing_keywords1, invoice_packing_keywords2])

template = """
根据用户给出的OCR后内容，识别出文档类型，提取特定信息并以JSON格式返回。执行以下步骤：
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
   - 确保日期信息有正确空格
   - 如果找不到对应信息，则json的值置为空
   - "Invoice No." 如果没有"Invoice No."，则查找 "Invoice Number"
   - "Amount" 以数字类型提取，只提取，不相加；
   - 如没有"Amount"，则找 "Total Amount"或"Total Value"或其他类似的词语，找不到置为0
   - 币种（Currency）应明确标出，例如 'USD'。
   - 如果没有"From" 信息,或者不像一个公司名称：则找：'Account Name' 、 'Beneficiary Name'、底部签名处或标题;大小写不敏感
   - 如果没有"Bill To"，则找'MESSRS'、'Purchaser' 或和发票购方相关词语；大小写不敏感
   - 如果"Bill To"提取到包含 'LOGISTICS' 或类似的物流公司信息，将""Bill To"和"Ship To"的值调换
   - 检查 "Bill To" 或 "From" ，如果有地址信息，删除它们
   - 检查 "Bill To" 或 "From" ，如果没正确分词，对他们进行分词; 如果有中文，直接提取，不要翻译
    - OCR的内容可能存在名词被切断、个别字母识别错误、对应错位等问题，你需要结合上下文语义进行综合判断，以抽取准确的关键信息。比如“Packing List”被识别成" Packihg
List"或"PACKINGLIST"
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


# 预处理 todo: 太hard code，后续引入规则引擎？
def before_extract(text):
    first_half, second_half = get_half(text)
    # 如果是packing list的，则直接返回
    if contain_keywords(first_half, packing_keywords):
        if not contain_keywords(first_half, invoice_packing_keywords1) and not contain_keywords(second_half,
                                                                                                invoice_packing_keywords2):
            return json.dumps({"Doc Type": "非发票：可能是装货单、waybill或其他"}, ensure_ascii=False, indent=4)

    # 如果是waybill或express的，则再检查一次不是发票，才返回
    if contain_keywords(text, express_keywords):
        if not contain_keywords(text, invoice_keywords):
            return json.dumps({"Doc Type": "非发票：可能是装货单、waybill或其他"}, ensure_ascii=False, indent=4)

    return None


# 后处理
def after_extract(result):
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

    return json.dumps(ret, ensure_ascii=False, indent=4)


def get_half(text):
    lines = text.splitlines()
    half_line_count = len(lines) // 2
    first_half_lines = lines[:half_line_count]
    second_half_lines = lines[half_line_count::]
    return '\n'.join(first_half_lines), '\n'.join(second_half_lines)


# 入口，包括事前、事中、事后处理
def extract_invoice(text, text_id=""):
    # 事前
    ret = before_extract(text)
    if ret:
        return ret

    # 事中
    ret = extract(text, text_id)

    # 事后
    return after_extract(ret)


def extract(text, text_id=""):
    global template
    sys_prompt = template
    # if is_markdown(text):
    #     sys_prompt = template.format(text_format="Markdown格式的")

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
        return rpa_extract(text, sys_prompt, text_id)

    model = "gpt-3.5-turbo-1106"
    if channel == channel.GPT4:
        model = "gpt-4-1106-preview"

    print("使用模型API：", model, text_id)
    try:
        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": text}
            ]
        )
    except Exception as e:
        print(f"调用openai出错：{e}")
        return json.dumps({"error": "fail: 调用大模型接口出错"})

    print("total tokens:", response.usage.total_tokens)
    print("system_fingerprint:", response.system_fingerprint)
    print(response.choices[0].message.content)

    return response.choices[0].message.content


def contain_keywords(text, excludes):
    # 将关键词列表转换为正则表达式
    # 使用 \s* 来匹配关键词中可能存在的空格或换行符
    keywords_pattern = '|'.join([keyword.replace(" ", r"\s*") for keyword in excludes])
    pattern = re.compile(keywords_pattern, re.IGNORECASE)

    ret = pattern.search(text)
    return bool(ret)


def rpa_extract(text, sys_prompt, reqid):
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
