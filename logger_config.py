import os
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

# 全局日志记录器字典
_loggers = {}

def setup_logger(name, log_dir="logs"):
    """设置日志记录器
    
    参数:
    name: 日志记录器名称，用于区分不同模块（如 'step1', 'step2', 'step3'）
    log_dir: 日志文件目录
    """
    # 如果已经创建过这个名称的日志记录器，直接返回
    if name in _loggers:
        return _loggers[name]
    
    # 确保日志目录存在
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 创建日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # 创建日志文件路径
    log_file = os.path.join(log_dir, f"{name}_{datetime.now().strftime('%Y%m%d')}.log")
    
    # 创建TimedRotatingFileHandler，每天轮转
    file_handler = TimedRotatingFileHandler(
        filename=log_file,
        when='midnight',  # 每天午夜轮转
        interval=1,       # 每1天轮转一次
        backupCount=1,    # 只保留1个备份文件（即只保留当天的日志）
        encoding='utf-8'
    )
    
    # 设置日志格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # 添加处理器到日志记录器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # 将日志记录器保存到全局字典
    _loggers[name] = logger
    
    return logger

# 创建各个模块的日志记录器
step1_logger = setup_logger('step1')
step2_logger = setup_logger('step2')
step3_logger = setup_logger('step3')
app_logger = setup_logger('app') 