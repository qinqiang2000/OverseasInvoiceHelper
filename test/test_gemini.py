import google.generativeai as genai
import os
from dotenv import load_dotenv
load_dotenv(override=True)

genai.configure(api_key=os.environ['GEMINI_API_KEY'], transport="rest")

# for model in genai.list_models():
#     pprint.pprint(model)

model = genai.GenerativeModel(model_name='gemini-pro')
response = model.generate_content("""Please summarise this document: Oracle Fusion Application建立在单一的统一数据模型之上，
具有一致的用户和开发人员体验，可跨模块（HCM、ERP、PPM、CX 和SCM） 连接端到端业务流程。
统一数据模型意味着所有应用模块共享相同的数据结构和业务逻辑。这样可以在不同业务功能之间实现一致且无缝的集成，减少数据冗余和复杂性。""")

print(response.text)