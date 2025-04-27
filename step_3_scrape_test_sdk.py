import os
import json
import re
import sys
import time
import traceback
import subprocess
from http import HTTPStatus
from dashscope import Application
import config
import db_utils
import logging
from datetime import datetime
import uuid
from urllib.parse import urlparse
import mysql.connector
from mysql.connector import pooling
from logger_config import step3_logger as logger

# 检查环境变量是否正确设置
if not config.check_env_vars():
    logger.error("环境变量配置错误，请检查.env文件")
    sys.exit(1)

# 创建数据库连接池
try:
    connection_pool = mysql.connector.pooling.MySQLConnectionPool(
        pool_name="sdk_pool",
        pool_size=5,
        **config.MYSQL_CONFIG
    )
    logger.info("MySQL连接池初始化成功")
except Exception as e:
    logger.error(f"MySQL连接池初始化失败: {str(e)}")
    sys.exit(1)

def clean_control_characters(text):
    """清理文本中的控制字符"""
    if not text:
        return ""
    # 移除所有控制字符（除了换行符和制表符）
    return re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)

def extract_domain(url):
    """从URL中提取域名，并移除查询参数"""
    try:
        parsed_url = urlparse(url)
        # 只保留scheme和netloc部分，舍弃路径、查询参数等
        domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
        logger.info(f"从URL [{url}] 提取的域名: {domain}")
        return domain
    except Exception as e:
        logger.error(f"提取域名时出错: {str(e)}")
        return ""

def get_homepage_info(url):
    """从数据库中获取URL对应的主页信息"""
    try:
        domain = extract_domain(url)
        if not domain:
            return None, None
            
        # 解析URL以获取netloc部分（供最后一次匹配使用）
        parsed_url = urlparse(url)
            
        # 从连接池获取连接
        conn = connection_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # 记录所有可能的主页URL，帮助调试
            cursor.execute("""
                SELECT link FROM homepage_urls WHERE active = 1
            """)
            all_urls = [row['link'] for row in cursor.fetchall()]
            # 不输出完整的URL列表，只输出数量
            logger.info(f"数据库中活跃的主页URL数量: {len(all_urls)}")
            
            # 先尝试直接匹配域名
            cursor.execute("""
                SELECT link, note, source 
                FROM homepage_urls 
                WHERE link = %s AND active = 1
            """, (domain,))
            
            result = cursor.fetchone()
            logger.info(f"精确匹配结果: {result}")
            
            # 如果找不到，尝试模糊匹配
            if not result:
                # 修正模糊匹配逻辑：检查URL是否以数据库中的链接为基础
                cursor.execute("""
                    SELECT link, note, source 
                    FROM homepage_urls 
                    WHERE %s LIKE CONCAT(link, '%%') AND active = 1
                """, (url,))
                result = cursor.fetchone()
                logger.info(f"模糊匹配结果: {result}")
            
            # 如果还找不到，尝试反向模糊匹配：检查数据库中的链接是否以域名为基础
            if not result:
                logger.info(f"尝试反向模糊匹配，域名: {domain}")
                cursor.execute("""
                    SELECT link, note, source 
                    FROM homepage_urls 
                    WHERE link LIKE CONCAT(%s, '%%') AND active = 1
                """, (domain,))
                result = cursor.fetchone()
                
                if result:
                    logger.info(f"反向模糊匹配成功: {result['link']}")
                else:
                    logger.info("反向模糊匹配失败")
                    
                    # 最后一次尝试：基于纯域名的模糊匹配（针对子域名或路径不匹配的情况）
                    cursor.execute("""
                        SELECT link, note, source 
                        FROM homepage_urls 
                        WHERE link LIKE %s AND active = 1
                    """, (f"%{parsed_url.netloc}%",))
                    result = cursor.fetchone()
                    logger.info(f"基于纯域名的模糊匹配结果: {result}")
            
            if result:
                return result['link'], f"{result['source']} - {result['note']}"
            
            return None, None
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        logger.error(f"获取主页信息时出错: {str(e)}")
        logger.error(traceback.format_exc())
        return None, None

def try_firecrawl_backup(url):
    """
    尝试使用firecrawl_news_crawler.py作为备用方案爬取内容
    
    参数:
        url (str): 要爬取的URL
        
    返回:
        dict: 成功时返回处理后的结果字典，失败时返回None
    """
    try:
        logger.info(f"尝试使用firecrawl_news_crawler.py作为备用方案爬取: {url}")
        
        # 构建调用firecrawl_news_crawler.py的命令
        cmd = [sys.executable, "firecrawl_news_crawler.py", url]
        
        # 运行命令并捕获输出
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # 尝试解析JSON输出
        if result.stdout.strip():
            try:
                json_result = json.loads(result.stdout)
                logger.info(f"firecrawl备用方案成功, 获取到标题: {json_result.get('title', '')[:30]}")
                return json_result
            except json.JSONDecodeError as e:
                logger.error(f"无法解析firecrawl返回的JSON: {e}")
                logger.error(f"输出内容: {result.stdout[:200]}...")
        else:
            logger.error("firecrawl备用方案返回空结果")
            
        return None
    except subprocess.CalledProcessError as e:
        logger.error(f"firecrawl备用方案执行失败: {e}")
        logger.error(f"stderr: {e.stderr[:200]}")
        return None
    except Exception as e:
        logger.error(f"使用firecrawl备用方案时出错: {e}")
        logger.error(traceback.format_exc())
        return None

def sdk_call(url, link_id=None, workflow_id=None):
    """使用SDK调用百炼应用处理URL"""
    start_time = datetime.now()
    logger.info(f"开始处理URL: {url}")
    
    # 生成唯一的link_id
    if link_id is None:
        link_id = f"link_{str(uuid.uuid4())[:8]}"
    
    # 如果没有workflow_id，创建一个
    if workflow_id is None:
        workflow_id = f"workflow_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        if len(workflow_id) > 50:
            workflow_id = workflow_id[:50]
    
    # 从数据库获取主页信息
    homepage_url, source_note = get_homepage_info(url)
    logger.info(f"URL对应的主页: {homepage_url or '未找到'}, 来源: {source_note or '无'}")
    
    # 更新处理状态
    db_utils.update_workflow_status(link_id, "PROCESSING", details={"url": url})
    
    # 设置最大重试次数和当前重试计数
    max_retries = 1  # 设置为1次重试
    retry_count = 0
    
    while retry_count <= max_retries:  # 允许初始尝试 + 最多2次重试
        try:
            # 如果是重试，添加日志并等待
            if retry_count > 0:
                wait_time = 10  # 设置为10秒等待时间
                logger.info(f"第 {retry_count} 次重试，等待 {wait_time} 秒...")
                time.sleep(wait_time)
                logger.info(f"开始第 {retry_count} 次重试处理URL: {url}")
            
            # 实际的API调用
            response = Application.call(
                api_key=config.DASHSCOPE_API_KEY,
                app_id=config.BAILIAN_APP_ID,
                prompt=url
            )
            response_code = response.status_code
            response_text = response.output.text if response_code == HTTPStatus.OK else response.message
            
            elapsed_time = (datetime.now() - start_time).total_seconds()
            
            # 处理失败的情况
            if response_code != HTTPStatus.OK:
                error_message = f'请求失败: {response_text}, 耗时: {elapsed_time:.2f}秒'
                logger.error(error_message)
                
                # 如果未达到最大重试次数，则继续重试
                if retry_count < max_retries:
                    retry_count += 1
                    continue
                
                # 达到最大重试次数，尝试使用firecrawl备用方案
                logger.info(f"主方案尝试{max_retries}次后失败，切换至firecrawl备用方案")
                firecrawl_result = try_firecrawl_backup(url)
                
                if firecrawl_result:
                    logger.info("firecrawl备用方案成功，使用其结果")
                    
                    # 添加元数据
                    firecrawl_result["url"] = url
                    firecrawl_result["link_id"] = link_id
                    firecrawl_result["workflow_id"] = workflow_id
                    firecrawl_result["homepage_url"] = url
                    firecrawl_result["source_note"] = source_note
                    
                    # 更新处理时间（如果不存在）
                    if "process_time" not in firecrawl_result:
                        elapsed_time = (datetime.now() - start_time).total_seconds()
                        firecrawl_result["process_time"] = f"{elapsed_time:.2f}秒"
                    
                    # 保存到数据库
                    success = save_to_db(link_id, firecrawl_result, True)
                    
                    # 更新工作流状态
                    if success:
                        db_utils.update_workflow_status(link_id, "COMPLETED", 
                                                     details={
                                                         "title": firecrawl_result.get('title', '')[:100],
                                                         "url": url,
                                                         "process_time": firecrawl_result.get("process_time", ""),
                                                         "method": "firecrawl_backup"
                                                     })
                    else:
                        db_utils.update_workflow_status(link_id, "FAILED", error="保存firecrawl结果到数据库失败")
                    
                    return json.dumps(firecrawl_result, ensure_ascii=False)
                
                # firecrawl备用方案也失败，更新状态为失败
                db_utils.update_workflow_status(link_id, "FAILED", error=error_message)
                
                # 构造错误响应数据
                result_data = {
                    "title": "",
                    "content": "",
                    "event_tags": [],
                    "space_tags": [],
                    "cat_tags": [],
                    "impact_factors": [],
                    "publish_time": "",
                    "importance": "低",
                    "state": ["爬取失败"],
                    "url": url,
                    "link_id": link_id,
                    "workflow_id": workflow_id,
                    "homepage_url": url,
                    "source_note": source_note,
                    "error": error_message,
                    "process_time": f"{elapsed_time:.2f}秒"
                }
                
                # 保存到数据库
                save_to_db(link_id, result_data, False)
                
                return json.dumps(result_data, ensure_ascii=False)
            
            # 处理成功的情况
            try:
                # 清理控制字符
                cleaned_text = clean_control_characters(response_text)
                logger.info(f"清理后的原始文本前100字符: {cleaned_text[:100]}")
                
                # 解析JSON
                result_data = json.loads(cleaned_text)
                
                # 详细记录解析后的标题字段
                title_value = result_data.get('title', '')
                logger.info(f"解析后的标题字段: [{title_value}]，长度: {len(title_value)}")
                # 检查标题字段是否包含不可见字符
                hex_title = ' '.join(hex(ord(c)) for c in title_value[:20]) if title_value else '空'
                logger.info(f"标题字段前20个字符的十六进制: {hex_title}")
                
                logger.info(f"成功解析返回的JSON，标题: {result_data.get('title', '')[:30]}")
                
                # 确保所有必要字段存在
                default_fields = {
                    "title": "",
                    "content": "",
                    "event_tags": [],
                    "space_tags": [],
                    "cat_tags": [],
                    "impact_factors": [],
                    "publish_time": "",
                    "importance": "低",
                    "state": ["爬取成功"]
                }
                
                # 用默认值填充缺失字段
                for field, default_value in default_fields.items():
                    if field not in result_data:
                        result_data[field] = default_value
                
                # 检查title和content是否为空，如果为空则重试
                if not result_data.get('title') or not result_data.get('content'):
                    logger.warning("标题或内容为空，需要重试")
                    if retry_count < max_retries:
                        retry_count += 1
                        continue
                    else:
                        logger.warning(f"已达到最大重试次数 {max_retries}，尝试使用firecrawl备用方案")
                        firecrawl_result = try_firecrawl_backup(url)
                        
                        if firecrawl_result:
                            logger.info("firecrawl备用方案成功，使用其结果")
                            
                            # 添加元数据
                            firecrawl_result["url"] = url
                            firecrawl_result["link_id"] = link_id
                            firecrawl_result["workflow_id"] = workflow_id
                            firecrawl_result["homepage_url"] = url
                            firecrawl_result["source_note"] = source_note
                            
                            # 更新处理时间（如果不存在）
                            if "process_time" not in firecrawl_result:
                                elapsed_time = (datetime.now() - start_time).total_seconds()
                                firecrawl_result["process_time"] = f"{elapsed_time:.2f}秒"
                            
                            # 保存到数据库
                            success = save_to_db(link_id, firecrawl_result, True)
                            
                            # 更新工作流状态
                            if success:
                                db_utils.update_workflow_status(link_id, "COMPLETED", 
                                                             details={
                                                                 "title": firecrawl_result.get('title', '')[:100],
                                                                 "url": url,
                                                                 "process_time": firecrawl_result.get("process_time", ""),
                                                                 "method": "firecrawl_backup"
                                                             })
                            else:
                                db_utils.update_workflow_status(link_id, "FAILED", error="保存firecrawl结果到数据库失败")
                            
                            return json.dumps(firecrawl_result, ensure_ascii=False)
                        else:
                            logger.warning(f"firecrawl备用方案也失败，使用最后一次获取的结果")
                
                # 记录impact_factors字段
                logger.info(f"影响因素: {result_data.get('impact_factors', [])}")
                
                # 添加元数据
                result_data["url"] = url
                result_data["link_id"] = link_id
                result_data["workflow_id"] = workflow_id
                result_data["homepage_url"] = url
                result_data["source_note"] = source_note
                result_data["process_time"] = f"{elapsed_time:.2f}秒"
                
                # 检查保存前的数据
                if 'title' in result_data:
                    logger.info(f"保存到数据库前的标题: [{result_data['title']}]")
                else:
                    logger.info("警告: 结果数据中没有title字段")
                
                # 保存到数据库
                success = save_to_db(link_id, result_data, True)
                
                # 更新工作流状态
                if success:
                    db_utils.update_workflow_status(link_id, "COMPLETED", 
                                                 details={
                                                     "title": result_data.get('title', '')[:100],
                                                     "url": url,
                                                     "process_time": f"{elapsed_time:.2f}秒"
                                                 })
                else:
                    db_utils.update_workflow_status(link_id, "FAILED", error="保存到数据库失败")
                
                return json.dumps(result_data, ensure_ascii=False)
                
            except json.JSONDecodeError as e:
                error_message = f"JSON解析错误: {str(e)}, 原始文本: {response_text[:100]}..."
                logger.error(error_message)
                
                # 如果未达到最大重试次数，则继续重试
                if retry_count < max_retries:
                    retry_count += 1
                    continue
                
                # 达到最大重试次数，尝试使用firecrawl备用方案
                logger.info(f"主方案JSON解析失败，切换至firecrawl备用方案")
                firecrawl_result = try_firecrawl_backup(url)
                
                if firecrawl_result:
                    logger.info("firecrawl备用方案成功，使用其结果")
                    
                    # 添加元数据
                    firecrawl_result["url"] = url
                    firecrawl_result["link_id"] = link_id
                    firecrawl_result["workflow_id"] = workflow_id
                    firecrawl_result["homepage_url"] = url
                    firecrawl_result["source_note"] = source_note
                    
                    # 更新处理时间（如果不存在）
                    if "process_time" not in firecrawl_result:
                        elapsed_time = (datetime.now() - start_time).total_seconds()
                        firecrawl_result["process_time"] = f"{elapsed_time:.2f}秒"
                    
                    # 保存到数据库
                    success = save_to_db(link_id, firecrawl_result, True)
                    
                    # 更新工作流状态
                    if success:
                        db_utils.update_workflow_status(link_id, "COMPLETED", 
                                                     details={
                                                         "title": firecrawl_result.get('title', '')[:100],
                                                         "url": url,
                                                         "process_time": firecrawl_result.get("process_time", ""),
                                                         "method": "firecrawl_backup"
                                                     })
                    else:
                        db_utils.update_workflow_status(link_id, "FAILED", error="保存firecrawl结果到数据库失败")
                    
                    return json.dumps(firecrawl_result, ensure_ascii=False)
                
                # 达到最大重试次数，更新状态为失败
                db_utils.update_workflow_status(link_id, "FAILED", error=error_message)
                
                # 构造错误响应数据
                result_data = {
                    "title": "",
                    "content": "",
                    "event_tags": [],
                    "space_tags": [],
                    "cat_tags": [],
                    "impact_factors": [],
                    "publish_time": "",
                    "importance": "低",
                    "state": ["爬取失败-JSON解析错误"],
                    "url": url,
                    "link_id": link_id,
                    "workflow_id": workflow_id,
                    "homepage_url": url,
                    "source_note": source_note,
                    "error": error_message,
                    "process_time": f"{elapsed_time:.2f}秒"
                }
                
                # 保存到数据库
                save_to_db(link_id, result_data, False)
                
                return json.dumps(result_data, ensure_ascii=False)
                
        except Exception as e:
            elapsed_time = (datetime.now() - start_time).total_seconds()
            error_message = f"SDK调用出错: {str(e)}"
            logger.error(f"{error_message}\n{traceback.format_exc()}")
            
            # 如果未达到最大重试次数，则继续重试
            if retry_count < max_retries:
                retry_count += 1
                logger.info(f"发生异常，进行第 {retry_count} 次重试")
                continue
            
            # 达到最大重试次数，尝试使用firecrawl备用方案
            logger.info(f"主方案异常失败，切换至firecrawl备用方案")
            firecrawl_result = try_firecrawl_backup(url)
            
            if firecrawl_result:
                logger.info("firecrawl备用方案成功，使用其结果")
                
                # 添加元数据
                firecrawl_result["url"] = url
                firecrawl_result["link_id"] = link_id
                firecrawl_result["workflow_id"] = workflow_id
                firecrawl_result["homepage_url"] = url
                firecrawl_result["source_note"] = source_note
                
                # 更新处理时间（如果不存在）
                if "process_time" not in firecrawl_result:
                    elapsed_time = (datetime.now() - start_time).total_seconds()
                    firecrawl_result["process_time"] = f"{elapsed_time:.2f}秒"
                
                # 保存到数据库
                success = save_to_db(link_id, firecrawl_result, True)
                
                # 更新工作流状态
                if success:
                    db_utils.update_workflow_status(link_id, "COMPLETED", 
                                                 details={
                                                     "title": firecrawl_result.get('title', '')[:100],
                                                     "url": url,
                                                     "process_time": firecrawl_result.get("process_time", ""),
                                                     "method": "firecrawl_backup"
                                                 })
                else:
                    db_utils.update_workflow_status(link_id, "FAILED", error="保存firecrawl结果到数据库失败")
                
                return json.dumps(firecrawl_result, ensure_ascii=False)
            
            # 达到最大重试次数，更新状态为失败
            db_utils.update_workflow_status(link_id, "FAILED", error=error_message)
            
            # 构造错误响应数据
            result_data = {
                "title": "",
                "content": "",
                "event_tags": [],
                "space_tags": [],
                "cat_tags": [],
                "impact_factors": [],
                "publish_time": "",
                "importance": "低",
                "state": ["爬取失败-系统错误"],
                "url": url,
                "link_id": link_id,
                "workflow_id": workflow_id,
                "homepage_url": url,
                "source_note": source_note,
                "error": error_message,
                "process_time": f"{elapsed_time:.2f}秒"
            }
            
            # 保存到数据库
            try:
                save_to_db(link_id, result_data, False)
            except Exception as db_error:
                logger.error(f"保存错误信息到数据库时出错: {str(db_error)}")
            
            return json.dumps(result_data, ensure_ascii=False)

def save_to_db(link_id, data, success):
    """保存结果到数据库"""
    try:
        # 构建内容和元数据对象
        title = data.get('title', '')
        logger.info(f"保存到DB函数中获取的标题: [{title}]，长度: {len(title)}")
        
        content = data.get('content', '')
        state = data.get('state', ['爬取成功' if success else '爬取失败'])
        
        # 处理发布日期
        publish_time = data.get('publish_time', '')
        # 验证日期格式
        try:
            if not publish_time:
                # 如果为空，设置为当前日期
                publish_time = datetime.now().strftime('%Y-%m-%d')
            else:
                # 尝试解析日期
                parsed_date = datetime.strptime(publish_time[:10], '%Y-%m-%d')
                publish_time = parsed_date.strftime('%Y-%m-%d')
        except ValueError:
            # 如果日期格式不正确，使用当前日期
            logger.warning(f"日期格式不正确: {publish_time}，使用当前日期")
            publish_time = datetime.now().strftime('%Y-%m-%d')
        
        # 构建内容对象
        content_obj = {
            'title': title,
            'content': content,
            'event_tags': data.get('event_tags', []),
            'space_tags': data.get('space_tags', []),
            'cat_tags': data.get('cat_tags', []),
            'impact_factors': data.get('impact_factors', []),
            'publish_time': publish_time,
            'importance': data.get('importance', '低'),
            'state': state
        }
        
        # 构建元数据对象 - 确保homepage_url是子链接URL
        metadata = {
            'url': data.get('url', ''),
            'link_id': link_id,
            'source_note': data.get('source_note', ''),
            'homepage_url': data.get('url', ''),  # 这里使用url字段作为homepage_url字段的值
            'process_time': data.get('process_time', ''),
            'success': success
        }
        
        # 调用db_utils保存内容
        workflow_id = data.get('workflow_id', link_id)
        content_type = 'article'
        
        result = db_utils.save_content(workflow_id, content_type, content_obj, metadata)
        if result:
            logger.info(f"数据保存成功，ID: {result}")
        else:
            logger.warning("数据保存失败，返回值为None")
        return result is not None
    except Exception as e:
        logger.error(f"保存到数据库失败: {str(e)}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    # 测试URL
    test_url = "http://example.com/test_article"
    
    try:
        logger.info(f"开始测试SDK调用，URL: {test_url}")
        result_json = sdk_call(test_url)
        
        # 解析结果，仅用于日志打印摘要
        try:
            result = json.loads(result_json)
            success = True if result.get("state") and "爬取成功" in result.get("state") else False
            
            if success:
                logger.info(f"爬取成功，标题: {result.get('title', '')[:50]}")
            else:
                logger.warning(f"爬取失败，错误: {result.get('error', '未知错误')}")
        except Exception as e:
            logger.error(f"解析结果失败: {str(e)}")
            
    except Exception as e:
        logger.error(f"运行SDK时出错: {str(e)}\n{traceback.format_exc()}") 