import os

from dotenv import load_dotenv
from openai import AzureOpenAI
import json

load_dotenv(override=True)

client = AzureOpenAI(
    api_key=os.environ['AZURE_OPENAI_API_KEY'],
    api_version=os.environ['OPENAI_API_VERSION'],
    azure_endpoint=os.environ['AZURE_OPENAI_ENDPOINT']
    )


class LLMAzureOpenAI:
    def generate_text(self, text, sys_prompt, reqid):
        print("使用模型API：azure ",os.environ['OPENAI_DEPLOYMENT_NAME'], reqid)
        try:
            response = client.chat.completions.create(
                model=os.environ['OPENAI_DEPLOYMENT_NAME'],  # model = "deployment_name"
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