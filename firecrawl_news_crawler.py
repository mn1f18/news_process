import os
import sys
import json
import uuid
import traceback
from datetime import datetime
from dotenv import load_dotenv
from firecrawl import FirecrawlApp
from dashscope import Application

# 加载环境变量
load_dotenv()

# 获取FireCrawl API密钥
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
MCP_BACKUP_APP_ID = os.getenv("MCP_BACKUP_APP_ID")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")

# 验证环境变量
if not FIRECRAWL_API_KEY:
    print("错误：未找到FIRECRAWL_API_KEY环境变量")
    sys.exit(1)
    
if not MCP_BACKUP_APP_ID:
    print("错误：未找到MCP_BACKUP_APP_ID环境变量")
    sys.exit(1)
    
if not DASHSCOPE_API_KEY:
    print("错误：未找到DASHSCOPE_API_KEY环境变量")
    sys.exit(1)

def create_error_response(url, error_message, stage, link_id=None, workflow_id=None, elapsed_time=None):
    """创建标准的错误响应"""
    if link_id is None:
        link_id = f"link_{str(uuid.uuid4())[:8]}"
    if workflow_id is None:
        workflow_id = f"workflow_{datetime.now().strftime('%Y%m%d%H%M%S')}"[:50]
    
    process_time = f"{elapsed_time:.2f}秒" if elapsed_time else "未计时"
    
    return {
        "title": "",
        "content": "",
        "event_tags": [],
        "space_tags": [],
        "cat_tags": [],
        "impact_factors": [],
        "publish_time": "",
        "importance": "低",
        "state": [f"爬取失败-{stage}"],
        "url": url,
        "link_id": link_id,
        "workflow_id": workflow_id,
        "error": error_message,
        "process_time": process_time
    }

def process_content_with_mcp_backup(markdown_content):
    """使用阿里云API处理Markdown内容"""
    try:
        # 调用阿里云API
        response = Application.call(
            api_key=DASHSCOPE_API_KEY,
            app_id=MCP_BACKUP_APP_ID,
            prompt=markdown_content  # 直接传入markdown内容作为prompt
        )
        
        if response.status_code != 200:
            return None
        
        # 尝试从响应中提取JSON
        try:
            result_text = response.output.text
            # 查找第一个{和最后一个}之间的内容
            start = result_text.find('{')
            end = result_text.rfind('}')
            if start != -1 and end != -1:
                json_str = result_text[start:end+1]
                json_result = json.loads(json_str)
                return json_result
            else:
                return None
        except json.JSONDecodeError:
            return None
            
    except Exception:
        return None

def scrape_news_article(url, link_id=None, workflow_id=None):
    """爬取新闻文章内容并使用阿里云API处理"""
    start_time = datetime.now()
    
    # 生成唯一标识符
    if link_id is None:
        link_id = f"link_{str(uuid.uuid4())[:8]}"
    if workflow_id is None:
        workflow_id = f"workflow_{datetime.now().strftime('%Y%m%d%H%M%S')}"[:50]
    
    # 初始化FireCrawl应用
    app = FirecrawlApp(api_key=FIRECRAWL_API_KEY)
    
    # 创建参数字典
    params = {
        "formats": ["markdown"],
        "removeBase64Images": True,
        "agent": {
            "model": "FIRE-1",
            "prompt": "只提取新闻文章的正文内容、标题和发布时间。不要包含广告、导航栏、侧边栏或其他非正文内容。确保内容格式清晰。"
        }
    }
    
    try:
        # 执行爬取
        result = app.scrape_url(url, params=params)
        
        # 如果API返回的是成功信息格式，获取data部分
        if isinstance(result, dict) and "data" in result:
            result = result.get("data", {})
        
        if not result or "markdown" not in result:
            elapsed_time = (datetime.now() - start_time).total_seconds()
            return create_error_response(url, "未获取到有效内容", "FireCrawl爬取失败", link_id, workflow_id, elapsed_time)
            
        # 获取Markdown内容
        markdown_content = result.get("markdown", "")
        
        if not markdown_content:
            elapsed_time = (datetime.now() - start_time).total_seconds()
            return create_error_response(url, "未获取到文章内容", "FireCrawl爬取失败", link_id, workflow_id, elapsed_time)
            
        # 使用阿里云API处理内容
        processed_result = process_content_with_mcp_backup(markdown_content)
        
        elapsed_time = (datetime.now() - start_time).total_seconds()
        
        if processed_result:
            # 设置状态为爬取成功
            if isinstance(processed_result, dict) and "state" not in processed_result:
                processed_result["state"] = ["爬取成功"]
                
            # 添加元数据
            processed_result["url"] = url
            processed_result["link_id"] = link_id
            processed_result["workflow_id"] = workflow_id
            processed_result["process_time"] = f"{elapsed_time:.2f}秒"
            
            # 确保所有必要字段存在
            default_fields = {
                "title": "",
                "content": "",
                "event_tags": [],
                "space_tags": [],
                "cat_tags": [],
                "impact_factors": [],
                "publish_time": "",
                "importance": "低"
            }
            
            # 用默认值填充缺失字段
            for field, default_value in default_fields.items():
                if field not in processed_result:
                    processed_result[field] = default_value
            
            return processed_result
        else:
            return create_error_response(url, "内容处理失败", "阿里云API处理失败", link_id, workflow_id, elapsed_time)
            
    except Exception as e:
        elapsed_time = (datetime.now() - start_time).total_seconds()
        return create_error_response(url, f"爬取错误: {str(e)}", "系统错误", link_id, workflow_id, elapsed_time)

def main():
    # 获取用户输入的URL
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("请输入要爬取的新闻文章URL: ")
    
    if not url:
        print("错误：URL不能为空")
        return
    
    # 爬取并处理文章
    result = scrape_news_article(url)
    
    # 输出结果
    if result:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"state": ["爬取失败"]}, ensure_ascii=False))

if __name__ == "__main__":
    main() 