
# 基础prompt
base_prompt = """
根据用户给出的OCR的内容，识别出文档类型，提取并记录以下信息：
-文档类型（Doc Type）: 识别出是否"Invoice"类型，不是则返回"other"。
-发票编号（Invoice No.）: 如果没有"Invoice No."，则查找"Invoice Number"。
-发票日期（Invoice Date）。
-币种（Currency）: 仅以其官方的三字母代码形式输出。例如：USD, CNY, CAD, AUD, GBP, JPY, DEM, HKD, FRF, CHF, VND等
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
-OCR的内容可能存在名词被切断、换行、个别字母识别错误、对应错位等问题，你需要结合上下文语义进行综合判断，以抽取准确的关键信息。比如“Packing List”被识别成" Packihg
List"或"PACKINGLIST"。
-不要自动翻译，保留原文。
-仅输出JSON结果，不包含其他文字。
"""

# 根据不同的每个LLM的习性，额外增加定制化的prompt
gemini_prompt = """
-"Bill To" 、"From"或"Ship To" 如果同时有中文和英文，只提取英文部分;不要生成中文
-"Bill To" 、"From"或"Ship To": 只提取公司名称，不要提取地址
-"Currency": 仅以其官方的三字母代码形式输出，不要有其他内容
"""