import os
import json
import re
from http import HTTPStatus
from dashscope import Application
import config

# 检查环境变量是否正确设置
if not config.check_env_vars():
    exit(1)

def clean_control_characters(text):
    """清理文本中的控制字符"""
    # 移除所有控制字符（除了换行符和制表符）
    return re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)

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
            
        # 尝试解析返回的文本为JSON
        try:
            # 清理控制字符
            cleaned_text = clean_control_characters(response.output.text)
            
            # 首先尝试直接解析
            json_data = json.loads(cleaned_text)
            
            # 处理内容中的换行符
            if 'content' in json_data:
                # 先替换实际的换行符为转义字符
                json_data['content'] = json_data['content'].replace('\n', '\\n')
                # 清理其他可能的控制字符
                json_data['content'] = clean_control_characters(json_data['content'])
            
            # 确保所有字段都是字符串类型或正确的数据类型
            for key in json_data:
                if isinstance(json_data[key], str):
                    json_data[key] = clean_control_characters(json_data[key])
            
            # 确保返回包含所有必要字段，如果缺少则提供默认值
            default_fields = {
                "title": "",
                "content": "",
                "event_tags": [],
                "space_tags": [],
                "cat_tags": [],
                "publish_time": "",
                "importance": "低",
                "state": ["爬取失败"]
            }
            
            # 用默认值填充缺失字段
            for field, default_value in default_fields.items():
                if field not in json_data:
                    json_data[field] = default_value
            
            return json.dumps(json_data, ensure_ascii=False)
            
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {str(e)}")
            # 如果解析失败，返回一个包含错误信息的JSON，使用新格式
            return json.dumps({
                "title": "",
                "content": "",
                "event_tags": [],
                "space_tags": [],
                "cat_tags": [],
                "publish_time": "",
                "importance": "低",
                "state": ["爬取失败"]
            }, ensure_ascii=False)
            
    except Exception as e:
        print(f"SDK调用出错: {str(e)}")
        return None

if __name__ == "__main__":
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