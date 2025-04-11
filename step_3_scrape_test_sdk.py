import os
from http import HTTPStatus
from dashscope import Application
import config

# 检查环境变量是否正确设置
if not config.check_env_vars():
    exit(1)

def sdk_call(prompt):
    """使用SDK调用百炼应用"""
    try:
        response = Application.call(
            api_key=config.DASHSCOPE_API_KEY,
            app_id=config.BAILIAN_APP_ID,
            prompt=prompt
        )
        
        if response.status_code != HTTPStatus.OK:
            print(f'请求失败: {response.message}')
            return None
            
        return response.output.text
    except Exception as e:
        print(f"SDK调用出错: {str(e)}")
        return None

# 爬取网页的提示
prompt = """
http://www.iea.agricultura.sp.gov.br/out/TerTexto.php?codTexto=16256 
"""

# 调用百炼应用
print("开始调用百炼应用(SDK方式)...")
response = sdk_call(prompt)

if response:
    print("\n================== 爬取结果 ==================\n")
    print(response)
else:
    print("调用失败，未获取到响应") 