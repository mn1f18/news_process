import os
import logging
import sys
import tempfile
import hashlib
import glob
import shutil
from logging.handlers import TimedRotatingFileHandler, RotatingFileHandler
from datetime import datetime, timedelta
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

def cleanup_old_logs(log_dir="logs", days_to_keep=2):
    """
    清理指定天数之前的日志文件
    
    参数:
    log_dir: 日志文件目录
    days_to_keep: 要保留的天数
    """
    try:
        if not os.path.exists(log_dir):
            return
            
        # 获取当前日期
        today = datetime.now()
        
        # 获取所有日志文件
        log_files = glob.glob(os.path.join(log_dir, "*.log"))
        log_files.extend(glob.glob(os.path.join(log_dir, "*.log.*")))  # 包含轮转的日志文件
        
        for log_file in log_files:
            try:
                # 从文件名中提取日期部分 (格式: name_YYYYMMDD_pidXXXX.log)
                filename = os.path.basename(log_file)
                parts = filename.split('_')
                
                # 检查文件名是否包含日期部分
                if len(parts) >= 2:
                    try:
                        # 尝试解析日期部分
                        date_part = None
                        for part in parts:
                            if len(part) == 8 and part.isdigit():  # YYYYMMDD格式
                                date_part = part
                                break
                                
                        if date_part:
                            file_date = datetime.strptime(date_part, '%Y%m%d')
                            
                            # 如果文件日期早于保留天数，则删除
                            if (today - file_date).days > days_to_keep:
                                os.remove(log_file)
                                print(f"已删除旧日志文件: {log_file}")
                    except (ValueError, IndexError):
                        # 如果无法解析日期，检查文件修改时间
                        file_mtime = datetime.fromtimestamp(os.path.getmtime(log_file))
                        if (today - file_mtime).days > days_to_keep:
                            os.remove(log_file)
                            print(f"已基于修改时间删除旧日志文件: {log_file}")
            except Exception as e:
                sys.stderr.write(f"清理日志文件时出错 {log_file}: {str(e)}\n")
                
    except Exception as e:
        sys.stderr.write(f"清理日志目录时出错: {str(e)}\n")

# 使用全局变量记录是否已经初始化了日志系统
_logger_initialized = False

def setup_logger(name, log_dir="logs"):
    """设置日志记录器
    
    参数:
    name: 日志记录器名称，用于区分不同模块（如 'step1', 'step2', 'step3'）
    log_dir: 日志文件目录
    """
    global _logger_initialized
    
    # 如果已经创建过这个名称的日志记录器，直接返回
    if name in _loggers:
        return _loggers[name]
    
    # 确保日志目录存在
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 每次设置日志时尝试清理旧日志文件
    cleanup_old_logs(log_dir, 2)  # 保留最近2天的日志
    
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
        backupCount=2,    # 保留2个备份文件（即保留当天和前一天的日志）
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

# 仅当为主进程时创建日志记录器
is_main_process = True
try:
    import multiprocessing
    current_process = multiprocessing.current_process()
    # 如果进程名不是MainProcess，则是子进程（如Flask的reloader进程）
    if current_process.name != 'MainProcess':
        is_main_process = False
except:
    pass

# 创建各个模块的日志记录器
if is_main_process:
    step1_logger = setup_logger('step1')
    step2_logger = setup_logger('step2')
    step3_logger = setup_logger('step3')
    app_logger = setup_logger('app')
else:
    # 对于非主进程，使用简化的日志记录器，不写入文件
    step1_logger = logging.getLogger('step1')
    step2_logger = logging.getLogger('step2')
    step3_logger = logging.getLogger('step3')
    app_logger = logging.getLogger('app')
    
    # 如果没有处理器，添加一个控制台处理器
    for logger in [step1_logger, step2_logger, step3_logger, app_logger]:
        if not logger.handlers:
            console_handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
            logger.setLevel(logging.INFO) 