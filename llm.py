from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)
client = OpenAI()

template = """
根据用户给出的内容，提取特定信息并以JSON格式返回。内容可能是发票、装箱单或其他类型。执行以下步骤：

1. 检查文档是否标记为"packing list"、"packing slip"、"装箱单"、"attached-sheet"等，或包含这些词汇。如果是，认定为非发票并返回错误代码和文档类型（例如：{{"err": "E0001", 
"msg": /*可能的文档类型*/}}）。

2. 如果文档是发票且包含如 'page 1 of 3' 的多页信息，但缺少 "total"、"Amount"、"总金额" 等关键词，返回错误代码和相关页数（例如：{{"err": "E0002", "msg": /*第几页*/}}）。

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


def extract_invoice(text, text_id=""):
    return """ {
  "Invoice No.": "91742377",
  "Invoice Date": "2023/04/20",
  "Currency": "USD",
  "Amount": 34950.00,
  "Bill To": "HISENSE BROADBAND MULTIMEDIA TECHNOLOGIES (HK) CO., LIMITED",
  "From": "WT MICROELECTRONICS (HK) LTD."
}"""
    # response = client.chat.completions.create(
    #     model="gpt-4-1106-preview",
    #     response_format={"type": "json_object"},
    #     messages=[
    #         {"role": "system", "content": template},
    #         {"role": "user", "content": text}
    #     ]
    # )
    #
    # print("total tokens:", response.usage.total_tokens)
    # print(response.choices[0].message.content)

    return response.choices[0].message.content