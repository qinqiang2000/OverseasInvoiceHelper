import json
import os
import logging
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)
client = OpenAI(api_key=os.environ['MOONSHOT_API_KEY'], base_url="https://api.moonshot.cn/v1")


class LLMMoonshot:
    def __init__(self, model):
        self.model = model

    def generate_text(self, text, sys_prompt, reqid):
        print("使用模型API：", self.model, reqid)
        try:
            response = client.chat.completions.create(
                model=self.model,
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

        content = response.choices[0].message.content
        first_brace_index = content.find('{')
        last_brace_index = content.rfind('}')
        text = content[first_brace_index:last_brace_index + 1]
        logging.info(f"{self.model}:{reqid} extract from response: {text}")

        return text