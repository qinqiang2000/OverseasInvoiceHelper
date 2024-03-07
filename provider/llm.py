import json
import os
import re
from enum import Enum
from opencc import OpenCC
from dateutil import parser

from provider.llm_azure import LLMAzureOpenAI
from provider.llm_gemini import LLMGemini
from provider.llm_moonshot import LLMMoonshot
from provider.llm_openai import LLMOpenAI
from provider.llm_rpa_chatgpt import ChatGPTRPA
from provider.prompt import base_prompt

packing_keywords = {"packing list", "packing slip", "Shipment Packlist", "装箱单", "Delivery Order", "送货单",
                    "attached-sheet", "WEIGHT MEMO", "清单明细", '清單明', "装箱明细", "装箱", "CONTENT LIST"}
express_keywords = {"waybill", "way bill", "express world", "Delivery Note", "Delivery No", "收单",
                    "Certificate of Compliance", "FedEx.", "FedEx。"}
logistics_keywords = {"LOGISTICS", "物流", "快递", "express world"}
invoice_keywords = {"COMMERCIAL INVOICE", "Invoice Date", "INV.DATE", "Invoice No", "INV.NO", "Invoice Number",
                    "Involce Date", "Involce No", "Involce Number"}
invoice_packing_keywords1 = {"INVOICE & PACKING", "INVOICE / PACKING", "INVOICE  PACKING"}
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


class Channel(Enum):
    MOCK = 1
    RPA = 2
    GPT4 = 3
    GPT35 = 4
    GEMINI_PRO = 5
    AZURE_OPENAI = 6
    MOONSHOT = 7


# 取环境变量LLM_MODEL的值，如果没有，则默认为GPT4
channel = Channel(int(os.getenv("LLM_MODEL", Channel.GPT4.value)))


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
            return json.dumps({"Doc Type": "others"}, ensure_ascii=False, indent=4)

    # 如果是waybill或express的，则再检查一次不是发票，才返回
    if contain_keywords(text, express_keywords):
        if not contain_keywords(text, invoice_keywords):
            return json.dumps({"Doc Type": "others"}, ensure_ascii=False, indent=4)

    return None


# 后处理
def after_extract(result):
    try:
        ret = json.loads(result)
    except Exception as e:
        print(f"json.loads出错：{e}")
        return """ {"Doc Type": "json.loads出错"}"""

    ship_to = ret.get("Ship To")
    bill_to = ret.get("Bill To")
    # 如果ship包含物流关键词，则删除
    if bill_to and contain_keywords(bill_to, logistics_keywords) \
            and ship_to and not contain_keywords(ship_to, logistics_keywords) :
        print(f"bill to 包含物流关键词：{bill_to}, 和{ship_to}替换")
        ret["Ship To"] = bill_to
        ret["Bill To"] = ship_to

    if "Ship To" in ret:
        ret.pop("Ship To")

    keys = ["Doc Type", "Invoice No.", "Invoice Date", "Currency", "Amount", "Bill To", "From", "error"]
    keys = [key.lower() for key in keys]

    # 遍历ret，如果有key不在keys中，则删除
    for key in list(ret.keys()):
        if key.lower() not in keys:
            ret.pop(key)

    # 转换日期为统一格式
    # ret["Invoice Date"] = convert_date(ret.get("Invoice Date"))

    # 遍历字典，并替换每个值中的换行符
    ret = {key: value.replace('\n', ' ') if isinstance(value, str) else value for key, value in ret.items()}

    return json.dumps(ret, ensure_ascii=False, indent=4)


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
    if channel == Channel.MOCK:
        return """ {
        "Doc Type": "Invoice",
          "Invoice No.": "4510044687",
          "Invoice Date": "2023/08/04",
          "Currency": "USD",
          "Amount": 4590.00,
          "Bill To": "HISENSE BROADBAND MULTIMEDIA TECHNOLOGIES (HK) CO., LIMITED",
          "From": "KONG TAK ELECTRONIC CO., LTD."
        }"""

    if channel == Channel.RPA:
        rpa = ChatGPTRPA()
        return rpa.generate_text(text, base_prompt, text_id)

    if channel == channel.GPT35:
        return LLMOpenAI("gpt-3.5-turbo-1106").generate_text(text, base_prompt, text_id)

    if channel == channel.GPT4:
        return LLMOpenAI("gpt-4-1106-preview").generate_text(text, base_prompt, text_id)

    if channel == channel.GEMINI_PRO:
        return LLMGemini("gemini-pro").generate_text(text, base_prompt, text_id)

    if channel == channel.AZURE_OPENAI:
        return LLMAzureOpenAI().generate_text(text, base_prompt, text_id)

    if channel == channel.MOONSHOT:
        return LLMMoonshot("moonshot-v1-8k").generate_text(text, base_prompt, text_id)
    return """ {"Doc Type": "LLM配置错误"}"""


def get_half(text):
    lines = text.splitlines()
    half_line_count = len(lines) // 2
    first_half_lines = lines[:half_line_count]
    second_half_lines = lines[half_line_count::]
    return '\n'.join(first_half_lines), '\n'.join(second_half_lines)


def convert_date(date_str):
    if date_str is None:
        return date_str

    try:
        # 解析日期字符串
        dt = parser.parse(date_str)
        # 格式化为 YYYY-MM-DD
        return dt.strftime('%Y-%m-%d')
    except ValueError:
        return date_str


def contain_keywords(text, excludes):
    # 将关键词列表转换为正则表达式
    # 使用 \s* 来匹配关键词中可能存在的空格或换行符
    keywords_pattern = '|'.join([keyword.replace(" ", r"\s*") for keyword in excludes])
    pattern = re.compile(keywords_pattern, re.IGNORECASE)

    ret = pattern.search(text)
    return bool(ret)