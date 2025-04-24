import os
import logging
import sys
import tempfile
import hashlib
from logging.handlers import TimedRotatingFileHandler, RotatingFileHandler
from datetime import datetime
import time

# 全局日志记录器字典
_loggers = {}

# 使用进程ID创建唯一标识符
def get_process_id():
    """获取当前进程的唯一标识符"""
    import os
    return os.getpid()

class SafeRotatingFileHandler(TimedRotatingFileHandler):
    """
    自定义的安全日志轮转处理器，避免Windows下文件锁定问题
    """
    def __init__(self, filename, when='h', interval=1, backupCount=0, encoding=None, 
                 delay=False, utc=False, atTime=None):
        TimedRotatingFileHandler.__init__(self, filename, when, interval, backupCount, 
                                         encoding, delay, utc, atTime)
        
    def doRollover(self):
        """
        重写日志轮转方法，增加错误处理和重试机制
        """
        try:
            # 尝试标准的轮转方法
            super().doRollover()
        except (FileNotFoundError, PermissionError) as e:
            # 如果出现权限错误或文件未找到，输出错误但不中断程序
            sys.stderr.write(f"无法轮转日志文件 {self.baseFilename}: {str(e)}\n")
            # 创建新的日志文件，不再尝试轮转
            if self.stream:
                self.stream.close()
                self.stream = None
            
            # 尝试创建新文件而不轮转
            try:
                self.stream = self._open()
            except Exception as e:
                sys.stderr.write(f"无法创建新的日志文件: {str(e)}\n")

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
    
    # 如果该日志记录器已有处理器，避免重复添加
    if logger.handlers:
        return logger
    
    # 获取进程ID作为文件名的一部分
    process_id = get_process_id()
    
    # 创建日志文件路径 - 使用日期和进程ID，避免同一天内不同进程冲突
    # 但相同进程重启后使用相同文件
    today = datetime.now().strftime('%Y%m%d')
    log_file = os.path.join(log_dir, f"{name}_{today}_pid{process_id}.log")
    
    # 使用自定义的安全轮转处理器
    file_handler = SafeRotatingFileHandler(
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