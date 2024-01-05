import json
import os
import re
from enum import Enum
from opencc import OpenCC
from dateutil import parser

from provider.llm_gemini import LLMGemini
from provider.llm_openai import LLMOpenAI
from provider.llm_rpa_chatgpt import ChatGPTRPA

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

template = """
根据用户给出的OCR的内容，识别出文档类型，提取并记录以下信息：
-文档类型（Doc Type）: 识别出是否"Invoice"类型，不是则返回"other"。
-发票编号（Invoice No.）: 如果没有"Invoice No."，则查找"Invoice Number"。
-发票日期（Invoice Date）。
-币种（Currency）: 应明确标出，例如CNY. USD. CAD. AUD. GBP等
-总金额（Amount）: 以数字类型提取，如果没有"Amount"，则找"Total Amount"或"Total Value"或其他类似的词语，找不到置为0。
-收票方（Bill To）: 如果没有"Bill To"，则找'MESSRS'、'Purchaser' 、'Customer'或其他和'购买方'同义的词语；大小写不敏感。
-开票方（From）: 如果没有"From" 信息, 或者不像一个公司名称，则找：'Account Name'、'Beneficiary Name'、底部签名处或标题; 大小写不敏感。
-Ship To

注意：
-识别出常见收票方和开票方的公司名称组成部分，如“Group”, “Corporation”, “Limited”, “Inc.”等。
-识别并分割紧凑排列的单词，尤其是公司名称，如“WaterWorldInternationalIndustrialLimited”，正确分词为“Water World International Industrial Limited”。
-确保日期信息有正确空格。
-如果找不到对应信息，则json的值置为空。
-"Bill To" 或 "From" 如果有地址信息，删除它们。
-"Bill To" 或 "From" 或 "ship to" 如果没正确分词，对他们进行分词。
-OCR的内容可能存在名词被切断、个别字母识别错误、对应错位等问题，你需要结合上下文语义进行综合判断，以抽取准确的关键信息。比如“Packing List”被识别成" Packihg
List"或"PACKINGLIST"
-仅输出JSON结果，不包含其他文字。
"""


class Channel(Enum):
    MOCK = 1
    RPA = 2
    GPT4 = 3
    GPT35 = 4
    GEMINI_PRO = 5


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
    ret = json.loads(result)

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

    keys = ["Doc Type", "Invoice No.", "Invoice Date", "Currency", "Amount", "Bill To", "From"]
    keys = [key.lower() for key in keys]

    # 遍历ret，如果有key不在keys中，则删除
    for key in list(ret.keys()):
        if key.lower() not in keys:
            ret.pop(key)

    # 转换日期为统一格式
    # ret["Invoice Date"] = convert_date(ret.get("Invoice Date"))

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
    global template
    sys_prompt = template

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
        return rpa.generate_text(text, sys_prompt, text_id)

    if channel == channel.GPT35:
        return LLMOpenAI("gpt-3.5-turbo-1106").generate_text(text, sys_prompt, text_id)

    if channel == channel.GPT4:
        return LLMOpenAI("gpt-4-1106-preview").generate_text(text, sys_prompt, text_id)

    if channel == channel.GEMINI_PRO:
        return LLMGemini("gemini-pro").generate_text(text, sys_prompt, text_id)

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