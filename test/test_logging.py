import logging
# 配置日志器的日志级别为debug,高于debug或等于debug的都会报出
logging.basicConfig(level=logging.DEBUG)
logging.debug('This is a debug log')
logging.info('This is a info log')
logging.warning('This is a warning log')
logging.error('This is a error log')
logging.critical('This is a critical log')