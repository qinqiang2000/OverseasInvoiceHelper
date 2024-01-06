import json
import logging
import google.generativeai as genai
import os
from dotenv import load_dotenv

from provider.prompt import gemini_prompt

logging.basicConfig(level=logging.DEBUG)

load_dotenv(override=True)

generation_config = {
    "temperature": 0,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}

genai.configure(api_key=os.environ['GEMINI_API_KEY'], transport="rest")


def before_extract(text):
    # 将text中的全角字符转换为半角字符
    text = text.replace("（", " (").replace("）", ") ").replace("：", ":").replace("，", ",").replace("。", ".")
    return text


class LLMGemini:
    def __init__(self, model_name):
        self.model_name = model_name
        self.model = genai.GenerativeModel(model_name=model_name,
                                           generation_config=generation_config)

    def generate_text(self, text, sys_prompt, reqid):
        logging.info(f"使用模型API：{self.model_name}, {reqid}")

        text = before_extract(text)
        try:
            prompt_parts = [sys_prompt
                            + gemini_prompt
                            # + "\n-\"Bill To\" 、\"From\"或\"Ship To\": 删除其中的换行符'\\n';\n"
                            + "```\n" + text + "\n```"]
            logging.info(f"{self.model_name}:{reqid} prompt_parts: {prompt_parts}")
            response = self.model.generate_content(prompt_parts)
            logging.info(f"{self.model_name}:{reqid} response: {response.text}")

            first_brace_index = response.text.find('{')
            last_brace_index = response.text.rfind('}')
            text = response.text[first_brace_index:last_brace_index + 1]
            logging.info(f"{self.model_name}:{reqid} extract from response: {text}")

            return text
        except Exception as e:
            print(f"调用gemini出错：{e}")
            return json.dumps({"error": "fail: 调用大模型接口出错"})
