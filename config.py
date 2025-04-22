import os
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# 加载.env文件
load_dotenv()

# 配置基础路径
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# 获取API密钥等环境变量
DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY')
BAILIAN_APP_ID = os.getenv('BAILIAN_APP_ID')
API_KEY = os.getenv('FIRECRAWL_API_KEY')
LINK_ANALYZER_APP_ID = os.getenv('LINK_ANALYZER_APP_ID')

# 最大重试次数
MAX_RETRIES = 3

# 数据库连接信息
# PostgreSQL
PG_CONFIG = {
    "host": os.getenv("PG_HOST", "localhost"),
    "port": int(os.getenv("PG_PORT", "5432")),
    "database": os.getenv("PG_DATABASE", "test_db"),
    "user": os.getenv("PG_USER", "postgres"),
    "password": os.getenv("PG_PASSWORD", ""),
}

# MySQL
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "database": os.getenv("MYSQL_DATABASE", "test_db"),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
}

# 常规配置项
CONFIG = {
    "log_level": os.getenv("LOG_LEVEL", "INFO"),
    "max_batch_size": int(os.getenv("MAX_BATCH_SIZE", "50")),
    "sdk_api_key": os.getenv("SDK_API_KEY", ""),
    "sdk_api_endpoint": os.getenv("SDK_API_ENDPOINT", ""),
    "sdk_timeout": int(os.getenv("SDK_TIMEOUT", "120")),
}

def check_env_vars():
    """检查环境变量是否正确设置"""
    required_vars = [
        ('DASHSCOPE_API_KEY', DASHSCOPE_API_KEY),
        ('BAILIAN_APP_ID', BAILIAN_APP_ID),
        ('FIRECRAWL_API_KEY', API_KEY),
        ('LINK_ANALYZER_APP_ID', LINK_ANALYZER_APP_ID),
        # 数据库连接信息
        ('PG_HOST', PG_CONFIG['host']),
        ('PG_USER', PG_CONFIG['user']),
        ('PG_PASSWORD', PG_CONFIG['password']),
        ('MYSQL_HOST', MYSQL_CONFIG['host']),
        ('MYSQL_USER', MYSQL_CONFIG['user']),
        ('MYSQL_PASSWORD', MYSQL_CONFIG['password'])
    ]
    
    all_good = True
    for var_name, var_value in required_vars:
        if not var_value:
            logging.error(f"环境变量 {var_name} 未设置或为空")
            all_good = False
    
    return all_good

# 配置日志函数
def setup_logger(name, log_file=None, level=None):
    """配置并返回一个日志记录器"""
    level = level or CONFIG["log_level"]
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    logger = logging.getLogger(name)
    logger.setLevel(numeric_level)
    
    # 清除现有处理程序，防止重复
    if logger.handlers:
        logger.handlers.clear()
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台处理程序
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理程序（如果指定了日志文件）
    if log_file:
        log_path = LOG_DIR / log_file
        file_handler = RotatingFileHandler(
            log_path, 
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

# 提供全局日志配置
def get_logger(name, log_file=None):
    """获取预配置的日志记录器"""
    return setup_logger(name, log_file)

# 获取全局配置值
def get_config(key, default=None):
    """获取配置值，如果不存在则返回默认值"""
    return CONFIG.get(key, default)

# 主日志记录器
logger = get_logger("config")

# 当直接运行此文件时，检查环境变量
if __name__ == "__main__":
    if check_env_vars():
        print("环境配置正确！")
        print(f"百炼API密钥: {DASHSCOPE_API_KEY[:5]}...{DASHSCOPE_API_KEY[-5:]}")
        print(f"百炼应用ID: {BAILIAN_APP_ID}")
        print(f"链接分析应用ID: {LINK_ANALYZER_APP_ID}")
        print(f"Firecrawl API密钥: {API_KEY[:5]}...{API_KEY[-5:]}")
    else:
        print("环境配置不完整，请检查.env文件") 