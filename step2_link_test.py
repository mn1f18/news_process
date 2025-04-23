import os
import json
import traceback
from http import HTTPStatus
from dashscope import Application
import config
import logging
from datetime import datetime
import uuid
import db_utils
from logger_config import step2_logger as logger

# 确保环境变量正确设置
if not config.check_env_vars():
    logger.error("环境变量配置错误，请检查.env文件")
    exit(1)

# 配置日志系统
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

class LinkAnalyzer:
    """链接分析器，判断链接是否需要爬取"""
    
    def __init__(self):
        """初始化链接分析器"""
        # 使用config.py中定义的APP_ID
        self.app_id = config.LINK_ANALYZER_APP_ID
        
        logger.info(f"初始化链接分析器，使用百炼应用ID: {self.app_id}")
        
    def _extract_json_from_text(self, text):
        """从文本中提取JSON内容"""
        try:
            # 查找第一个{和最后一个}之间的内容
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1:
                json_str = text[start:end+1]
                return json.loads(json_str)
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {str(e)}, 文本: {text[:200]}...")
            return None
        
    def analyze_link(self, link, link_id=None, workflow_id=None):
        """
        分析单个链接，返回分析结果和链接ID
        
        参数:
        link - 要分析的链接
        link_id - 链接ID，如果为None则自动生成
        workflow_id - 工作流ID，如果为None则将link_id作为workflow_id
        """
        start_time = datetime.now()
        
        if link_id is None:
            link_id = str(uuid.uuid4())
            
        if workflow_id is None:
            workflow_id = link_id  # 如果单独调用，则使用link_id作为workflow_id
            
        try:
            # 更新链接状态为"分析中"
            db_utils.update_workflow_status(link_id, "ANALYZING", details={"link": link})
            
            logger.info(f"开始分析链接: {link}, ID: {link_id}")
            
            response = Application.call(
                api_key=config.DASHSCOPE_API_KEY,
                app_id=self.app_id,
                prompt=link  # 直接传入链接作为prompt
            )
            
            elapsed_time = (datetime.now() - start_time).total_seconds()
            
            if response.status_code != HTTPStatus.OK:
                error_message = f'请求失败: {response.message}, 耗时: {elapsed_time:.2f}秒'
                logger.error(error_message)
                db_utils.update_workflow_status(link_id, "FAILED", error=error_message)
                
                # 保存分析结果到数据库，标记为失败
                db_utils.save_link_analysis(
                    link_id, 
                    link, 
                    False,  # is_valid = False
                    {"error": error_message, "response_code": response.status_code}, 
                    workflow_id,
                    0,  # confidence = 0
                    error_message
                )
                
                return None, link_id
                
            # 解析返回的JSON
            result = self._extract_json_from_text(response.output.text)
            if result:
                # 判断链接是否有效
                is_valid = result.get('need_crawl', False)
                status = "VALID" if is_valid else "INVALID"
                
                # 添加处理时间和原始链接到结果中
                result["process_time"] = f"{elapsed_time:.2f}秒"
                result["link"] = link
                
                # 更新链接状态
                db_utils.update_workflow_status(link_id, status, details=result)
                
                # 保存分析结果到数据库
                confidence = result.get('confidence', 0)
                reason = result.get('reason', '')
                db_utils.save_link_analysis(
                    link_id, 
                    link, 
                    is_valid, 
                    result, 
                    workflow_id,  # 使用传入的workflow_id
                    confidence, 
                    reason
                )
                
                logger.info(f"链接分析完成，链接: {link}, 结果: {status}, 理由: {reason}, 耗时: {elapsed_time:.2f}秒")
                return result, link_id
            else:
                error_message = f"无法从响应中提取JSON: {response.output.text[:200]}..."
                logger.error(error_message)
                db_utils.update_workflow_status(link_id, "FAILED", error=error_message)
                
                # 保存分析结果到数据库，标记为失败
                db_utils.save_link_analysis(
                    link_id, 
                    link, 
                    False,  # is_valid = False
                    {"error": error_message, "raw_response": response.output.text[:500]}, 
                    workflow_id,
                    0,  # confidence = 0
                    error_message
                )
                
                return None, link_id
                
        except Exception as e:
            elapsed_time = (datetime.now() - start_time).total_seconds()
            error_message = f"分析链接时出错: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_message)
            
            db_utils.update_workflow_status(link_id, "FAILED", error=str(e))
            
            # 保存分析结果到数据库，标记为失败
            db_utils.save_link_analysis(
                link_id, 
                link, 
                False,  # is_valid = False
                {"error": str(e)}, 
                workflow_id,
                0,  # confidence = 0
                str(e)
            )
            
            return None, link_id

    def process_links(self, links, batch_id=None):
        """处理多个链接，支持批处理ID"""
        start_time = datetime.now()
        
        if batch_id is None:
            batch_id = f"batch_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
        # 确保workflow_id不超过50个字符
        workflow_id = batch_id
        if len(workflow_id) > 50:
            workflow_id = workflow_id[:50]
            
        results = {
            'batch_id': batch_id,
            'valid': [],
            'invalid': [],
            'failed': [],
            'link_ids': {}
        }
        
        total_links = len(links)
        processed_links = 0
        
        # 更新批次工作流状态为开始
        db_utils.update_workflow_status(workflow_id, "ANALYSIS_START", 
                                      details={"total_links": total_links})
        
        logger.info(f"开始批量分析 {total_links} 个链接，批次ID: {batch_id}")
        
        for link in links:
            processed_links += 1
            # 为每个链接生成唯一ID，但不作为workflow_id使用
            link_id = f"{batch_id[:35]}_{processed_links}"
            logger.info(f"\n正在分析链接 [{processed_links}/{total_links}]: {link}")
            
            try:
                # 调用百炼应用分析链接
                response = Application.call(
                    api_key=config.DASHSCOPE_API_KEY,
                    app_id=self.app_id,
                    prompt=link  # 直接传入链接作为prompt
                )
                
                if response.status_code != HTTPStatus.OK:
                    logger.error(f'请求失败: {response.message}')
                    results['failed'].append(link)
                    results['link_ids'][link] = link_id
                    
                    # 保存分析结果到数据库，标记为失败
                    db_utils.save_link_analysis(
                        link_id, 
                        link, 
                        False,  # is_valid = False
                        {"error": response.message, "response_code": response.status_code}, 
                        workflow_id,
                        0,  # confidence = 0
                        response.message
                    )
                    
                    continue
                    
                # 解析返回的JSON
                result = self._extract_json_from_text(response.output.text)
                if result:
                    # 判断链接是否有效
                    is_valid = result.get('need_crawl', False)
                    status = "VALID" if is_valid else "INVALID"
                    
                    # 保存分析结果到数据库
                    confidence = result.get('confidence', 0)
                    reason = result.get('reason', '')
                    db_utils.save_link_analysis(
                        link_id, 
                        link, 
                        is_valid, 
                        result, 
                        workflow_id,  # 使用批次工作流ID
                        confidence, 
                        reason
                    )
                    
                    # 将链接ID添加到结果中
                    results['link_ids'][link] = link_id
                    
                    if is_valid:
                        results['valid'].append(link)
                        logger.info(f"有效链接: {link}")
                        logger.info(f"原因: {result.get('reason', '')}")
                        logger.info(f"置信度: {result.get('confidence', 0)}")
                    else:
                        results['invalid'].append(link)
                        logger.info(f"无效链接: {link}")
                        logger.info(f"原因: {result.get('reason', '')}")
                        logger.info(f"置信度: {result.get('confidence', 0)}")
                else:
                    error_message = f"无法从响应中提取JSON: {response.output.text[:200]}..."
                    logger.error(error_message)
                    results['failed'].append(link)
                    results['link_ids'][link] = link_id
                    
                    # 保存分析结果到数据库，标记为失败
                    db_utils.save_link_analysis(
                        link_id, 
                        link, 
                        False,  # is_valid = False
                        {"error": error_message, "raw_response": response.output.text[:500]}, 
                        workflow_id,
                        0,  # confidence = 0
                        error_message
                    )
                
            except Exception as e:
                error_message = f"分析链接时出错: {str(e)}\n{traceback.format_exc()}"
                logger.error(error_message)
                results['failed'].append(link)
                results['link_ids'][link] = link_id
                
                # 保存分析结果到数据库，标记为失败
                db_utils.save_link_analysis(
                    link_id, 
                    link, 
                    False,  # is_valid = False
                    {"error": str(e)}, 
                    workflow_id,
                    0,  # confidence = 0
                    str(e)
                )
        
        # 保存批量分析结果
        db_utils.save_analysis_batch(workflow_id, batch_id, results)
        
        # 计算总耗时
        elapsed_time = (datetime.now() - start_time).total_seconds()
        
        # 更新批次工作流状态为完成
        db_utils.update_workflow_status(workflow_id, "ANALYZED", 
                                      details={
                                          "valid_count": len(results['valid']),
                                          "invalid_count": len(results['invalid']),
                                          "failed_count": len(results['failed']),
                                          "total_time": f"{elapsed_time:.2f}秒"
                                      })
        
        logger.info(f"批量分析完成，总耗时: {elapsed_time:.2f}秒")
        logger.info(f"有效链接: {len(results['valid'])}, 无效链接: {len(results['invalid'])}, 失败链接: {len(results['failed'])}")
        
        return results

    def reanalyze_failed_links(self, max_retries=3):
        """重新分析失败的链接"""
        start_time = datetime.now()
        
        # 生成新的批次工作流ID
        reanalysis_batch_id = f"reanalysis_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        workflow_id = reanalysis_batch_id
        if len(workflow_id) > 50:
            workflow_id = workflow_id[:50]
            
        # 从数据库获取所有失败的链接
        failed_status = "FAILED"
        failed_workflows = db_utils.get_all_workflow_status(failed_status)
        
        retry_links = []
        link_id_map = {}  # 用于存储原始link_id和链接的映射
        
        for wf_id, data in failed_workflows.items():
            # 跳过已超过重试次数的工作流
            retry_count = sum(1 for status in data.get('history', []) 
                             if status.get('status') == failed_status)
            
            if retry_count >= max_retries:
                continue
                
            # 获取该工作流中的所有链接
            cursor = None
            conn = None
            try:
                import psycopg2
                import psycopg2.extras
                conn = psycopg2.connect(**config.PG_CONFIG)
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                
                # 查询该工作流下所有失败的链接
                cursor.execute("""
                    SELECT link_id, link FROM step2_link_analysis 
                    WHERE workflow_id = %s AND is_valid = FALSE
                """, (wf_id,))
                
                for row in cursor.fetchall():
                    link_id = row['link_id']
                    link = row['link']
                    retry_links.append(link)
                    link_id_map[link] = link_id
                    
            except Exception as e:
                error_message = f"获取失败链接时出错: {str(e)}\n{traceback.format_exc()}"
                logger.error(error_message)
            finally:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
        
        if not retry_links:
            logger.info("没有需要重试的失败链接")
            return []
        
        logger.info(f"开始重新分析 {len(retry_links)} 个失败的链接")
        
        # 更新工作流状态
        db_utils.update_workflow_status(workflow_id, "REANALYSIS_START", 
                                      details={"failed_links_count": len(retry_links)})
        
        # 使用process_links处理失败链接
        results = self.process_links(retry_links, reanalysis_batch_id)
        
        # 计算总耗时
        elapsed_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"重新分析完成，总耗时: {elapsed_time:.2f}秒")
        logger.info(f"有效链接: {len(results['valid'])}, " 
                   f"无效链接: {len(results['invalid'])}, "
                   f"失败链接: {len(results['failed'])}")
        
        return results

if __name__ == "__main__":
    try:
        # 初始化链接分析器
        analyzer = LinkAnalyzer()
        
        # 测试链接列表
        test_links = [
            "https://example.com/agriculture-news",
            "https://example.com/farming-policy",
            "https://example.com/weather-impact"
        ]
        
        # 使用一个明确的batch_id进行测试
        test_batch_id = f"test_batch_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # 分析链接
        logger.info(f"开始测试分析 {len(test_links)} 个链接")
        results = analyzer.process_links(test_links, test_batch_id)
        
        # 打印分析结果统计
        logger.info("\n分析结果统计:")
        logger.info(f"批次ID: {results['batch_id']}")
        logger.info(f"有效链接数量: {len(results['valid'])}")
        logger.info(f"无效链接数量: {len(results['invalid'])}")
        logger.info(f"失败链接数量: {len(results['failed'])}")
        
    except KeyboardInterrupt:
        logger.info("检测到用户中断，程序退出")
    except Exception as e:
        logger.error(f"程序执行出错: {str(e)}\n{traceback.format_exc()}") 