import os
from dotenv import load_dotenv

# 加载.env文件中的环境变量
load_dotenv()

# 百炼API配置
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
BAILIAN_APP_ID = os.getenv("BAILIAN_APP_ID")

# Firecrawl API配置
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")

# Firecrawl 应用配置
API_KEY = FIRECRAWL_API_KEY  # 与step_1中的API_KEY变量名保持一致
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 5  # 重试延迟时间（秒）

# 检查关键环境变量是否存在
def check_env_vars():
    missing_vars = []
    if not DASHSCOPE_API_KEY:
        missing_vars.append("DASHSCOPE_API_KEY")
    if not BAILIAN_APP_ID:
        missing_vars.append("BAILIAN_APP_ID")
    if not FIRECRAWL_API_KEY:
        missing_vars.append("FIRECRAWL_API_KEY")
    
    if missing_vars:
        print(f"错误: 以下环境变量未设置: {', '.join(missing_vars)}")
        print("请确保.env文件存在并包含所有必要的环境变量")
        return False
    return True

# 当直接运行此文件时，检查环境变量
if __name__ == "__main__":
    if check_env_vars():
        print("环境配置正确！")
        print(f"百炼API密钥: {DASHSCOPE_API_KEY[:5]}...{DASHSCOPE_API_KEY[-5:]}")
        print(f"百炼应用ID: {BAILIAN_APP_ID}")
        print(f"Firecrawl API密钥: {FIRECRAWL_API_KEY[:5]}...{FIRECRAWL_API_KEY[-5:]}")
    else:
        print("环境配置不完整，请检查.env文件") 