import os
import sys
import json
import uuid
import traceback
from datetime import datetime
from dotenv import load_dotenv
from firecrawl import FirecrawlApp
from dashscope import Application
import time

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

def process_content_with_mcp_backup(markdown_content, max_retries=1):
    """使用阿里云API处理Markdown内容，添加重试机制"""
    retry_count = 0
    
    while retry_count <= max_retries:  # 允许初始尝试 + 最多max_retries次重试
        try:
            # 如果是重试，等待一段时间
            if retry_count > 0:
                wait_time = 5  # 设置为5秒等待时间
                time.sleep(wait_time)
            
            # 调用阿里云API
            response = Application.call(
                api_key=DASHSCOPE_API_KEY,
                app_id=MCP_BACKUP_APP_ID,
                prompt=markdown_content,  # 直接传入markdown内容作为prompt
                timeout=30  # 30秒超时
            )
            
            if response.status_code != 200:
                # 如果未达到最大重试次数，则继续重试
                if retry_count < max_retries:
                    retry_count += 1
                    continue
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
                    
                    # 检查重要字段是否存在
                    if not json_result.get('title') or not json_result.get('content'):
                        # 如果关键字段为空且未达到最大重试次数，则重试
                        if retry_count < max_retries:
                            retry_count += 1
                            continue
                    
                    return json_result
                else:
                    # 如果未达到最大重试次数，则继续重试
                    if retry_count < max_retries:
                        retry_count += 1
                        continue
                    return None
            except json.JSONDecodeError:
                # 如果未达到最大重试次数，则继续重试
                if retry_count < max_retries:
                    retry_count += 1
                    continue
                return None
                
        except Exception:
            # 如果未达到最大重试次数，则继续重试
            if retry_count < max_retries:
                retry_count += 1
                continue
            return None
    
    return None

def scrape_news_article(url, link_id=None, workflow_id=None, max_retries=1):
    """爬取新闻文章内容并使用阿里云API处理，添加重试机制"""
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
        "timeout": 60,  # 60秒超时
        "agent": {
            "model": "FIRE-1",
            "prompt": "只提取新闻文章的正文内容、标题和发布时间。不要包含广告、导航栏、侧边栏或其他非正文内容。确保内容格式清晰。"
        }
    }
    
    retry_count = 0
    
    while retry_count <= max_retries:  # 允许初始尝试 + 最多max_retries次重试
        try:
            # 如果是重试，等待一段时间
            if retry_count > 0:
                wait_time = 5  # 设置为5秒等待时间
                time.sleep(wait_time)
            
            # 执行爬取
            result = app.scrape_url(url, params=params)
            
            # 如果API返回的是成功信息格式，获取data部分
            if isinstance(result, dict) and "data" in result:
                result = result.get("data", {})
            
            if not result or "markdown" not in result:
                # 如果未达到最大重试次数，则继续重试
                if retry_count < max_retries:
                    retry_count += 1
                    continue
                
                elapsed_time = (datetime.now() - start_time).total_seconds()
                return create_error_response(url, "未获取到有效内容", "FireCrawl爬取失败", link_id, workflow_id, elapsed_time)
                
            # 获取Markdown内容
            markdown_content = result.get("markdown", "")
            
            if not markdown_content:
                # 如果未达到最大重试次数，则继续重试
                if retry_count < max_retries:
                    retry_count += 1
                    continue
                
                elapsed_time = (datetime.now() - start_time).total_seconds()
                return create_error_response(url, "未获取到文章内容", "FireCrawl爬取失败", link_id, workflow_id, elapsed_time)
                
            # 使用阿里云API处理内容
            processed_result = process_content_with_mcp_backup(markdown_content, max_retries)
            
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
                # 如果未达到最大重试次数，则继续重试
                if retry_count < max_retries:
                    retry_count += 1
                    continue
                
                return create_error_response(url, "内容处理失败", "阿里云API处理失败", link_id, workflow_id, elapsed_time)
                
        except Exception as e:
            # 如果未达到最大重试次数，则继续重试
            if retry_count < max_retries:
                retry_count += 1
                continue
            
            elapsed_time = (datetime.now() - start_time).total_seconds()
            return create_error_response(url, f"爬取错误: {str(e)}", "系统错误", link_id, workflow_id, elapsed_time)
    
    # 如果所有重试都失败，返回一个通用错误
    elapsed_time = (datetime.now() - start_time).total_seconds()
    return create_error_response(url, "所有重试都失败", "系统错误", link_id, workflow_id, elapsed_time)

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
    
    # 输出结果，不使用缩进以确保与step_3兼容
    if result:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(json.dumps({"state": ["爬取失败"]}, ensure_ascii=False))

if __name__ == "__main__":
    main() 