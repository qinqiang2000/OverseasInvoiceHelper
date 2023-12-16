import json
import logging
import google.generativeai as genai
import os
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)

load_dotenv(override=True)

generation_config = {
  "temperature": 0,
  "top_p": 1,
  "top_k": 1,
  "max_output_tokens": 2048,
}
safety_settings = [
  {
    "category": "HARM_CATEGORY_HARASSMENT",
    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
  },
  {
    "category": "HARM_CATEGORY_HATE_SPEECH",
    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
  },
  {
    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
  },
  {
    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
  }
]

genai.configure(api_key=os.environ['GEMINI_API_KEY'], transport="rest")


class LLMGemini:
    def __init__(self, model_name):
        self.model_name = model_name
        self.model = genai.GenerativeModel(model_name=model_name,
                              generation_config=generation_config,
                              safety_settings=safety_settings)

    def generate_text(self, text, sys_prompt, reqid):
        logging.info(f"使用模型API：{self.model_name}, {reqid}")
        try:
            prompt = (sys_prompt
                      + "\n-\"Bill To\" 或 \"From\" 如果同时有中文和英文，只提取英文部分"
                      +"\n用户给的内容如下：\n```\n" + text + "\n```")
            response = self.model.generate_content(prompt)
            logging.info(f"{self.model_name}:{reqid} response: {response.text}")

            first_brace_index = response.text.find('{')
            last_brace_index = response.text.rfind('}')
            text = response.text[first_brace_index:last_brace_index + 1]
            logging.info(f"{self.model_name}:{reqid} extract from response: {response.text}")

            return text
        except Exception as e:
            print(f"调用gemini出错：{e}")
            return json.dumps({"error": "fail: 调用大模型接口出错"})
