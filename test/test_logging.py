import logging
from enum import Enum
import os

from dotenv import load_dotenv

load_dotenv(override=True)

# 配置日志器的日志级别为debug,高于debug或等于debug的都会报出
logging.basicConfig(level=logging.DEBUG)
logging.debug('This is a debug log')
logging.info('This is a info log')
logging.warning('This is a warning log')
logging.error('This is a error log')
logging.critical('This is a critical log')


class Channel(Enum):
    MOCK = 1
    RPA = 2
    GPT4 = 3
    GPT35 = 4


channel = Channel(int(os.getenv("LLM_MODEL", Channel.GPT4.value)))
print(channel)
