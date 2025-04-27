import os
import json
import logging
import time
import traceback
from datetime import datetime
import uuid
from flask import Flask, request, jsonify
import threading
import queue
import atexit

# 添加APScheduler库导入
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.memory import MemoryJobStore

# 导入我们的组件
from step_1_homepage_scrape import HomepageScraper
from step2_link_test import LinkAnalyzer
from step_3_scrape_test_sdk import sdk_call
import db_utils
from db_utils import pg_connection
import config
from logger_config import app_logger as logger

# 创建Flask应用
app = Flask(__name__)
# 设置JSON编码，不转义中文字符
app.config['JSON_AS_ASCII'] = False

# 创建调度器
scheduler = BackgroundScheduler(jobstores={'default': MemoryJobStore()})
scheduler.start()

# 确保数据目录存在
data_dir = "data"
if not os.path.exists(data_dir):
    os.makedirs(data_dir)

# 确保日志目录存在
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# 任务队列
task_queue = queue.Queue()

class WorkflowManager:
    """工作流管理器，负责协调三个步骤之间的工作流"""
    
    def __init__(self):
        """初始化工作流管理器"""
        logger.info("初始化工作流管理器")
        # 初始化组件
        self.homepage_scraper = HomepageScraper()
        self.link_analyzer = LinkAnalyzer()
        
    def generate_workflow_id(self):
        """生成唯一的工作流ID"""
        return str(uuid.uuid4())
    
    def update_workflow_status(self, workflow_id, status, details=None, error=None):
        """更新工作流状态"""
        logger.debug(f"更新工作流状态: {workflow_id} => {status}")
        
        try:
            # 使用数据库函数更新工作流状态
            success = db_utils.update_workflow_status(workflow_id, status, details, error)
            
            if not success:
                logger.error(f"更新工作流状态失败: {workflow_id}")
                return False
                
            return True
        except Exception as e:
            logger.error(f"更新工作流状态时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def get_workflow_status(self, workflow_id):
        """获取工作流状态"""
        logger.debug(f"获取工作流状态: {workflow_id}")
        
        try:
            # 从数据库获取工作流状态
            workflow_status = db_utils.get_workflow_status(workflow_id)
            
            if workflow_status is None:
                logger.warning(f"未找到工作流: {workflow_id}")
                return None
                
            return workflow_status
        except Exception as e:
            logger.error(f"获取工作流状态时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    
    def get_all_workflow_status(self, status_filter=None):
        """获取所有工作流状态"""
        logger.debug(f"获取所有工作流状态, 过滤条件: {status_filter}")
        
        try:
            # 从数据库获取所有工作流状态
            all_statuses = db_utils.get_all_workflow_status(status_filter)
            
            if not all_statuses:
                logger.warning(f"没有找到任何工作流状态记录")
                return []
                
            return all_statuses
        except Exception as e:
            logger.error(f"获取所有工作流状态时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return []
            
    def save_analysis_result(self, workflow_id, result_type, results):
        """保存分析结果"""
        logger.debug(f"保存分析结果: workflow_id={workflow_id}, type={result_type}")
        
        try:
            # 使用数据库保存内容
            content_id = db_utils.save_content(
                workflow_id=workflow_id,
                content_type=result_type,
                content=results
            )
            
            if content_id:
                logger.info(f"分析结果已保存: content_id={content_id}")
                return True
            else:
                logger.error(f"保存分析结果失败")
                return False
        except Exception as e:
            logger.error(f"保存分析结果时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return False
            
    def get_analysis_result(self, workflow_id, result_type):
        """获取分析结果"""
        logger.debug(f"获取分析结果: workflow_id={workflow_id}, type={result_type}")
        
        try:
            # 使用数据库获取内容
            content = db_utils.get_content(
                workflow_id=workflow_id,
                content_type=result_type
            )
            
            if content is None:
                logger.warning(f"未找到分析结果: workflow_id={workflow_id}, type={result_type}")
            
            return content
        except Exception as e:
            logger.error(f"获取分析结果时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    
    def start_homepage_scraping(self, workflow_id=None):
        """启动主页抓取流程"""
        if workflow_id is None:
            workflow_id = f"workflow_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            # 确保不超过50个字符
            if len(workflow_id) > 50:
                workflow_id = workflow_id[:50]
            
        try:
            # 更新工作流状态
            self.update_workflow_status(workflow_id, "SCRAPING_START")
            
            # 运行主页抓取
            logger.info(f"开始主页抓取，工作流ID: {workflow_id}")
            new_links_data = self.homepage_scraper.check_for_new_links()
            
            if not new_links_data:
                logger.info("没有发现新链接，工作流完成")
                self.update_workflow_status(workflow_id, "COMPLETED", 
                                            details={"message": "没有发现新链接"})
                return workflow_id, []
            
            # 从新链接数据中提取链接
            all_links = []
            for homepage_url, data in new_links_data.items():
                # 使用site作为分类标签
                for link in data.get('new_links', []):
                    all_links.append({
                        'link': link,
                        'source': data.get('source', ''),
                        'note': data.get('note', ''),
                        'homepage': homepage_url,
                        'batch_id': data.get('batch_id', '')
                    })
            
            # 更新工作流状态
            self.update_workflow_status(workflow_id, "SCRAPED", 
                                       details={"links_found": len(all_links)})
            
            logger.info(f"主页抓取完成，发现 {len(all_links)} 个新链接")
            return workflow_id, all_links
            
        except Exception as e:
            error_msg = f"主页抓取过程出错: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.update_workflow_status(workflow_id, "FAILED", error=error_msg)
            return workflow_id, []
    
    def get_newly_discovered_links(self):
        """获取新发现的链接"""
        try:
            # 使用db_utils从数据库获取新链接
            links = db_utils.get_newly_discovered_links()
            logger.info(f"从数据库获取到 {len(links)} 组新链接数据")
            return links
        except Exception as e:
            error_msg = f"获取新链接数据时出错: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            return {}

    def get_latest_links(self, max_links=50):
        """获取最新的一批链接"""
        try:
            # 使用db_utils从数据库获取最新链接
            links = db_utils.get_latest_links(max_links)
            logger.info(f"从数据库获取到 {len(links)} 个最新链接")
            return links
        except Exception as e:
            error_msg = f"获取最新链接时出错: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            return []

    def analyze_links(self, links, workflow_id):
        """分析链接，判断哪些需要爬取"""
        try:
            if not links:
                logger.warning("没有链接需要分析")
                self.update_workflow_status(workflow_id, "COMPLETED", 
                                          details={"message": "没有链接需要分析"})
                return workflow_id, None
            
            # 更新工作流状态
            self.update_workflow_status(workflow_id, "ANALYZING", 
                                       details={"links_count": len(links)})
            
            # 对于复杂链接对象，提取链接URL
            if isinstance(links[0], dict):
                link_urls = [link['link'] for link in links]
            else:
                link_urls = links
            
            # 使用链接分析器进行分析
            logger.info(f"开始分析 {len(link_urls)} 个链接")
            results = self.link_analyzer.process_links(link_urls, batch_id=workflow_id)
            
            # 更新工作流状态
            analysis_stats = {
                "valid_count": len(results['valid']),
                "invalid_count": len(results['invalid']),
                "failed_count": len(results['failed']),
                "total_count": len(link_urls)
            }
            
            self.update_workflow_status(workflow_id, "ANALYZED", details=analysis_stats)
            
            logger.info(f"链接分析完成，有效链接: {len(results['valid'])}, 无效链接: {len(results['invalid'])}, 失败: {len(results['failed'])}")
            
            return workflow_id, results
        except Exception as e:
            error_msg = f"分析链接时出错: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.update_workflow_status(workflow_id, "FAILED", error=error_msg)
            return workflow_id, None
    
    def save_analysis_results(self, results, workflow_id):
        """保存分析结果到数据库"""
        try:
            if not results:
                logger.warning("没有分析结果需要保存")
                return False
                
            # 结果已经在process_links中保存到数据库
            logger.info(f"分析结果已保存到数据库，工作流ID: {workflow_id}")
            return True
            
        except Exception as e:
            error_msg = f"保存分析结果时出错: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            return False
    
    def analyze_latest_links(self, max_links=50):
        """分析最新的链接"""
        try:
            # 创建新的工作流ID
            workflow_id = f"analyze_latest_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            if len(workflow_id) > 50:
                workflow_id = workflow_id[:50]
                
            # 更新工作流状态
            self.update_workflow_status(workflow_id, "STARTED", 
                                       details={"max_links": max_links})
                
            # 获取最新链接
            logger.info(f"开始获取最新的 {max_links} 个链接")
            latest_links = self.get_latest_links(max_links)
            
            if not latest_links:
                logger.warning("没有找到任何链接")
                self.update_workflow_status(workflow_id, "COMPLETED", 
                                          details={"message": "没有找到任何链接"})
                return workflow_id, None
                
            logger.info(f"获取到 {len(latest_links)} 个最新链接")
            
            # 分析链接
            _, results = self.analyze_links([link['link'] for link in latest_links], workflow_id)
            
            return workflow_id, results
            
        except Exception as e:
            error_msg = f"分析最新链接时出错: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            if workflow_id:
                self.update_workflow_status(workflow_id, "FAILED", error=error_msg)
            return workflow_id, None
    
    def run_complete_workflow(self):
        """运行完整的工作流：抓取 -> 分析 -> 处理有效链接"""
        workflow_id = f"complete_workflow_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        if len(workflow_id) > 50:
            workflow_id = workflow_id[:50]
            
        try:
            # 更新工作流状态
            self.update_workflow_status(workflow_id, "STARTED")
            
            # 步骤1：抓取新链接
            logger.info("步骤1：开始抓取新链接")
            _, links = self.start_homepage_scraping(workflow_id)
            
            if not links:
                logger.info("没有发现新链接，工作流完成")
                self.update_workflow_status(workflow_id, "COMPLETED", 
                                          details={"message": "没有发现新链接"})
                return workflow_id, None
                
            # 步骤2：分析链接
            logger.info(f"步骤2：开始分析 {len(links)} 个链接")
            _, results = self.analyze_links([link['link'] for link in links], workflow_id)
            
            if not results:
                logger.warning("链接分析没有结果，工作流完成")
                self.update_workflow_status(workflow_id, "COMPLETED", 
                                          details={"message": "链接分析没有结果"})
                return workflow_id, None
                
            # 步骤3：处理有效链接
            if results['valid']:
                logger.info(f"步骤3：处理 {len(results['valid'])} 个有效链接")
                processed_links = self.process_valid_links(workflow_id, results['valid'])
                
                self.update_workflow_status(workflow_id, "COMPLETED", 
                                          details={
                                              "valid_links": len(results['valid']),
                                              "processed_links": len(processed_links),
                                              "invalid_links": len(results['invalid']),
                                              "failed_links": len(results['failed'])
                                          })
                                          
                return workflow_id, {
                    "valid": results['valid'],
                    "processed": processed_links,
                    "invalid": results['invalid'],
                    "failed": results['failed']
                }
            else:
                logger.info("没有有效链接需要处理，工作流完成")
                self.update_workflow_status(workflow_id, "COMPLETED", 
                                          details={"message": "没有有效链接需要处理"})
                return workflow_id, results
                
        except Exception as e:
            error_msg = f"运行完整工作流时出错: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.update_workflow_status(workflow_id, "FAILED", error=error_msg)
            return workflow_id, None
    
    def process_valid_links(self, workflow_id=None, input_links=None, max_links=50):
        """处理有效链接，进行爬取和分析"""
        if workflow_id is None:
            workflow_id = f"process_links_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            if len(workflow_id) > 50:
                workflow_id = workflow_id[:50]
                
        try:
            # 更新工作流状态
            self.update_workflow_status(workflow_id, "PROCESSING")
            
            links_to_process = []
            
            # 如果提供了输入链接，直接使用
            if input_links:
                links_to_process = input_links[:max_links]
                logger.info(f"使用提供的链接，总计 {len(links_to_process)} 个")
            else:
                # 否则，从数据库获取最新的有效链接
                valid_links = db_utils.get_valid_links(max_links=max_links)
                if valid_links:
                    links_to_process = [link['link'] for link in valid_links]
                    logger.info(f"从数据库获取 {len(links_to_process)} 个有效链接")
                    
            if not links_to_process:
                logger.warning("没有有效链接需要处理")
                self.update_workflow_status(workflow_id, "COMPLETED", 
                                          details={"message": "没有有效链接需要处理"})
                return []
                
            # 使用SDK处理每个链接
            processed_links = []
            total_links = len(links_to_process)
            
            for i, link in enumerate(links_to_process):
                try:
                    logger.info(f"处理链接 [{i+1}/{total_links}]: {link}")
                    
                    # 为每个链接生成唯一的link_id
                    link_id = f"{workflow_id}_link_{i+1}"
                    
                    # 使用SDK处理链接
                    result_json = sdk_call(link, link_id, workflow_id)
                    
                    # 检查结果
                    if result_json:
                        processed_links.append(link)
                        logger.info(f"链接处理成功: {link}")
                    else:
                        logger.warning(f"链接处理失败: {link}")
                        
                except Exception as e:
                    error_msg = f"处理链接时出错 {link}: {str(e)}\n{traceback.format_exc()}"
                    logger.error(error_msg)
                    
            # 更新工作流状态
            self.update_workflow_status(workflow_id, "COMPLETED", 
                                      details={
                                          "total_links": total_links,
                                          "processed_links": len(processed_links),
                                          "failed_links": total_links - len(processed_links)
                                      })
                                      
            logger.info(f"链接处理完成，成功: {len(processed_links)}, 失败: {total_links - len(processed_links)}")
            return processed_links
            
        except Exception as e:
            error_msg = f"处理有效链接时出错: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.update_workflow_status(workflow_id, "FAILED", error=error_msg)
            return []

    def run_complete_extended_workflow(self):
        """运行扩展的完整工作流，包含四个步骤"""
        workflow_id = f"extended_workflow_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        if len(workflow_id) > 50:
            workflow_id = workflow_id[:50]
            
        try:
            # 更新工作流状态
            self.update_workflow_status(workflow_id, "STARTED")
            
            # 步骤1：抓取新链接
            results = self.handle_step1(workflow_id)
            
            if not results:
                return workflow_id, None
                
            # 步骤2：分析链接
            results = self.handle_step2(workflow_id, results.get('links'))
            
            if not results:
                return workflow_id, None
                
            # 步骤3：处理有效链接
            results = self.handle_step3(workflow_id, results.get('valid_links'))
            
            if results:
                self.update_workflow_status(workflow_id, "COMPLETED", 
                                          details={"message": "扩展工作流完成"})
                                          
            return workflow_id, results
            
        except Exception as e:
            error_msg = f"运行扩展工作流时出错: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.update_workflow_status(workflow_id, "FAILED", error=error_msg)
            return workflow_id, None
            
    def handle_step1(self, workflow_id, news_source=None):
        """处理步骤1：抓取新链接"""
        try:
            logger.info("步骤1：开始抓取新链接")
            
            # 更新工作流状态
            self.update_workflow_status(workflow_id, "STEP1_STARTED")
            
            # 抓取新链接
            _, links = self.start_homepage_scraping(workflow_id)
            
            if not links:
                logger.info("没有发现新链接，步骤1完成")
                self.update_workflow_status(workflow_id, "STEP1_COMPLETED", 
                                          details={"message": "没有发现新链接"})
                return None
                
            logger.info(f"步骤1完成，发现 {len(links)} 个新链接")
            
            self.update_workflow_status(workflow_id, "STEP1_COMPLETED", 
                                      details={"links_found": len(links)})
                                      
            return {
                "links": links,
                "count": len(links)
            }
            
        except Exception as e:
            error_msg = f"处理步骤1时出错: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.update_workflow_status(workflow_id, "STEP1_FAILED", error=error_msg)
            return None
    
    def handle_step2(self, workflow_id, links=None):
        """处理步骤2：分析链接"""
        try:
            logger.info("步骤2：开始分析链接")
            
            # 更新工作流状态
            self.update_workflow_status(workflow_id, "STEP2_STARTED")
            
            if not links:
                # 如果没有提供链接，从数据库获取最新链接
                links = self.get_latest_links(50)
                
            if not links:
                logger.warning("没有链接需要分析，步骤2完成")
                self.update_workflow_status(workflow_id, "STEP2_COMPLETED", 
                                          details={"message": "没有链接需要分析"})
                return None
                
            # 分析链接
            if isinstance(links[0], dict):
                link_urls = [link['link'] for link in links]
            else:
                link_urls = links
                
            _, results = self.analyze_links(link_urls, workflow_id)
            
            if not results:
                logger.warning("链接分析没有结果，步骤2完成")
                self.update_workflow_status(workflow_id, "STEP2_COMPLETED", 
                                          details={"message": "链接分析没有结果"})
                return None
                
            logger.info(f"步骤2完成，有效链接: {len(results['valid'])}, 无效链接: {len(results['invalid'])}, 失败: {len(results['failed'])}")
            
            self.update_workflow_status(workflow_id, "STEP2_COMPLETED", 
                                      details={
                                          "valid_count": len(results['valid']),
                                          "invalid_count": len(results['invalid']),
                                          "failed_count": len(results['failed'])
                                      })
                                      
            return {
                "valid_links": results['valid'],
                "invalid_links": results['invalid'],
                "failed_links": results['failed'],
                "link_ids": results['link_ids']
            }
            
        except Exception as e:
            error_msg = f"处理步骤2时出错: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.update_workflow_status(workflow_id, "STEP2_FAILED", error=error_msg)
            return None
    
    def handle_step3(self, workflow_id, links=None):
        """处理步骤3：处理有效链接"""
        try:
            logger.info("步骤3：开始处理有效链接")
            
            # 更新工作流状态
            self.update_workflow_status(workflow_id, "STEP3_STARTED")
            
            # 查找最近的工作流ID
            latest_workflow = None
            try:
                # 查找最近的工作流ID
                with db_utils.pg_connection() as cursor:
                    cursor.execute(
                        """SELECT workflow_id FROM step0_workflows 
                        WHERE current_status = 'ANALYZED' 
                        ORDER BY created_at DESC LIMIT 1"""
                    )
                    result = cursor.fetchone()
                    if result:
                        latest_workflow = result['workflow_id']
                        logger.info(f"找到最近的工作流ID: {latest_workflow}")
            except Exception as e:
                logger.error(f"查找最近的工作流ID时出错: {str(e)}")
                logger.error(traceback.format_exc())
                # 继续处理，使用提供的链接或不带过滤的获取链接
            
            if not links:
                # 如果没有提供链接，从数据库获取最新工作流的有效链接
                valid_links_data = db_utils.get_valid_links(max_links=50, latest_workflow_id=latest_workflow)
                if valid_links_data:
                    links = [link['link'] for link in valid_links_data]
                    logger.info(f"从最新工作流 {latest_workflow or '(未指定)'} 获取了 {len(links)} 个有效链接")
                
            if not links:
                logger.warning("没有有效链接需要处理，步骤3完成")
                self.update_workflow_status(workflow_id, "STEP3_COMPLETED", 
                                          details={"message": "没有有效链接需要处理"})
                return None
                
            # 更新工作流状态，显示正在处理的链接数量
            self.update_workflow_status(workflow_id, "STEP3_PROCESSING", 
                                      details={
                                          "total_links": len(links),
                                          "source_workflow": latest_workflow
                                      })
            
            # 处理有效链接
            try:
                processed_links = self.process_valid_links(workflow_id, links, 50)
                
                logger.info(f"步骤3完成，成功处理了 {len(processed_links)} 个链接，共 {len(links)} 个")
                
                self.update_workflow_status(workflow_id, "STEP3_COMPLETED", 
                                          details={
                                              "processed_count": len(processed_links),
                                              "total_count": len(links),
                                              "source_workflow": latest_workflow
                                          })
                                          
                return {
                    "processed_links": processed_links,
                    "total_links": len(links),
                    "source_workflow": latest_workflow
                }
            except Exception as e:
                error_msg = f"处理链接时出错: {str(e)}\n{traceback.format_exc()}"
                logger.error(error_msg)
                self.update_workflow_status(workflow_id, "STEP3_FAILED", 
                                          error=error_msg,
                                          details={
                                              "total_links": len(links),
                                              "source_workflow": latest_workflow
                                          })
                raise  # 重新抛出异常，让外层捕获
            
        except Exception as e:
            error_msg = f"处理步骤3时出错: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.update_workflow_status(workflow_id, "STEP3_FAILED", error=error_msg)
            return None

# 创建工作流管理器实例
workflow_manager = WorkflowManager()

# 线程函数：处理任务队列
def task_worker():
    while True:
        try:
            # 从队列获取任务
            task = task_queue.get()
            
            if task['type'] == 'scrape':
                workflow_manager.start_homepage_scraping(task.get('workflow_id'))
            elif task['type'] == 'analyze':
                workflow_manager.analyze_links(task['links'], task['workflow_id'])
            elif task['type'] == 'complete_workflow':
                workflow_manager.run_complete_workflow()
            elif task['type'] == 'analyze_latest':
                workflow_manager.analyze_latest_links(task.get('max_links', 50))
            elif task['type'] == 'process_valid_links':
                workflow_manager.process_valid_links(
                    task.get('workflow_id'),
                    task.get('input_links'),
                    task.get('max_links', 50)
                )
            elif task['type'] == 'extended_workflow':
                # 直接执行工作流，不再处理定时任务逻辑
                workflow_manager.run_complete_extended_workflow()
            
            # 标记任务完成
            task_queue.task_done()
            
        except Exception as e:
            logger.error(f"任务处理出错: {e}")
            # 即使出错也要标记任务完成，避免阻塞队列
            task_queue.task_done()
        
        # 短暂休眠，避免CPU占用过高
        time.sleep(0.1)

# 启动工作线程
worker_thread = threading.Thread(target=task_worker, daemon=True)
worker_thread.start()

# 程序退出时关闭调度器
atexit.register(lambda: scheduler.shutdown())

# 路由: 主页
@app.route('/')
def home():
    return jsonify({
        'status': 'ok',
        'message': 'News Processing System API'
    })

# 路由: 步骤1 - 主页抓取
@app.route('/api/step1', methods=['POST'])
def step1():
    workflow_id = f"workflow_step1_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # 将任务添加到队列
    task_queue.put({
        'type': 'scrape',
        'workflow_id': workflow_id
    })
    
    return jsonify({
        'status': 'accepted',
        'workflow_id': workflow_id,
        'message': 'Homepage scraping task has been queued'
    })

# 路由: 步骤2 - 链接分析（指定链接）
@app.route('/api/step2', methods=['POST'])
def step2():
    data = request.json
    
    if not data or 'links' not in data:
        return jsonify({
            'status': 'error',
            'message': 'Please provide links field'
        }), 400
    
    workflow_id = data.get('workflow_id', f"workflow_step2_{datetime.now().strftime('%Y%m%d%H%M%S')}")
    
    # 将任务添加到队列
    task_queue.put({
        'type': 'analyze',
        'links': data['links'],
        'workflow_id': workflow_id
    })
    
    return jsonify({
        'status': 'accepted',
        'workflow_id': workflow_id,
        'message': 'Link analysis task has been queued'
    })

# 路由: 步骤2 - 分析最新抓取的链接
@app.route('/api/step2/latest', methods=['POST'])
def step2_latest():
    # 允许空的请求体或非JSON请求
    try:
        data = request.json or {}
    except:
        data = {}
    
    max_links = data.get('max_links', 50)
    
    # 修改：确保workflow_id不超过50个字符
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    workflow_id = f"workflow_step2_{timestamp}"
    # 确保不超过50个字符
    if len(workflow_id) > 50:
        workflow_id = workflow_id[:50]
    
    # 将任务添加到队列
    task_queue.put({
        'type': 'analyze_latest',
        'max_links': max_links,
        'workflow_id': workflow_id
    })
    
    return jsonify({
        'status': 'accepted',
        'workflow_id': workflow_id,
        'message': f'Latest links analysis task has been queued, max analysis of {max_links} links'
    })

# 路由: 步骤3 - 内容抓取分析
@app.route('/api/step3', methods=['POST'])
def step3():
    # 允许空的请求体或非JSON请求
    try:
        data = request.json or {}
    except:
        data = {}
    
    workflow_id = data.get('workflow_id', f"workflow_step3_{datetime.now().strftime('%Y%m%d%H%M%S')}")
    max_links = data.get('max_links', 50)
    input_links = data.get('links')
    
    # 将任务添加到队列
    task_queue.put({
        'type': 'process_valid_links',
        'workflow_id': workflow_id,
        'input_links': input_links,
        'max_links': max_links
    })
    
    return jsonify({
        'status': 'accepted',
        'workflow_id': workflow_id,
        'message': f'Valid links processing task has been queued, max processing of {max_links} links'
    })

# 路由: 完整工作流（步骤1+2）
@app.route('/api/workflow/step1to2', methods=['POST'])
def step1to2_workflow():
    workflow_id = f"workflow_step1to2_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # 将任务添加到队列
    task_queue.put({
        'type': 'complete_workflow',
        'workflow_id': workflow_id
    })
    
    return jsonify({
        'status': 'accepted',
        'workflow_id': workflow_id,
        'message': 'Complete workflow (step1-2) has been queued. Step 2 will only analyze the latest links, not all links.'
    })

# 路由: 完整工作流（步骤1+2+3）
@app.route('/api/workflow/all', methods=['POST'])
def all_workflow():
    # 允许空的请求体或非JSON请求
    try:
        data = request.json or {}
    except:
        data = {}
    
    # 获取定时运行间隔（分钟）
    interval_minutes = data.get('interval_minutes')
    
    workflow_id = f"workflow_all_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    # 确保不超过50个字符
    if len(workflow_id) > 50:
        workflow_id = workflow_id[:50]
    
    # 首先执行一次工作流
    task_queue.put({
        'type': 'extended_workflow',
        'workflow_id': workflow_id
    })
    
    # 如果设置了定时间隔，使用调度器添加定时任务
    if interval_minutes:
        # 创建调度任务的唯一ID
        job_id = f"scheduled_job_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # 如果同名任务已存在，先移除
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
        
        # 添加定时任务，使用 IntervalTrigger
        scheduler.add_job(
            run_scheduled_workflow,
            IntervalTrigger(minutes=interval_minutes),
            id=job_id,
            kwargs={'workflow_id_prefix': f"scheduled_{workflow_id}"},
            replace_existing=True
        )
        
        logger.info(f"已添加定时任务 {job_id}，每 {interval_minutes} 分钟执行一次")
        
        return jsonify({
            'status': 'accepted',
            'workflow_id': workflow_id,
            'job_id': job_id,
            'message': f'Extended workflow (step1-2-3) has been queued and scheduled to run every {interval_minutes} minutes.'
        })
    else:
        return jsonify({
            'status': 'accepted',
            'workflow_id': workflow_id,
            'message': 'Extended workflow (step1-2-3) has been queued. Step 2 will only analyze the latest links, not all links.'
        })

# 路由: 获取工作流状态
@app.route('/api/workflow/<workflow_id>', methods=['GET'])
def get_workflow_status(workflow_id):
    status = workflow_manager.get_workflow_status(workflow_id)
    
    if status:
        return jsonify({
            'status': 'ok',
            'workflow_id': workflow_id,
            'data': status
        })
    else:
        return jsonify({
            'status': 'error',
            'message': f'Workflow {workflow_id} not found'
        }), 404

# 路由: 获取所有工作流状态
@app.route('/api/workflows', methods=['GET'])
def get_all_workflows():
    status_filter = request.args.get('status')
    statuses = workflow_manager.get_all_workflow_status(status_filter)
    
    return jsonify({
        'status': 'ok',
        'count': len(statuses),
        'data': statuses
    })

# 路由: 获取链接状态
@app.route('/api/link/<link_id>', methods=['GET'])
def get_link_status(link_id):
    # 从数据库获取链接信息
    link_data = db_utils.get_link_analysis(link_id)
    
    if link_data:
        return jsonify({
            'status': 'ok',
            'link_id': link_id,
            'data': link_data,
            'type': 'database'
        })
    
    # 找不到链接
    return jsonify({
        'status': 'error',
        'message': f'Link {link_id} not found'
    }), 404

# 路由: 获取所有定时任务
@app.route('/api/scheduler/jobs', methods=['GET'])
def get_scheduler_jobs():
    try:
        jobs = []
        for job in scheduler.get_jobs():
            next_run = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else None
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': next_run,
                'trigger': str(job.trigger)
            })
        
        return jsonify({
            'status': 'ok',
            'count': len(jobs),
            'jobs': jobs
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error getting scheduler jobs: {str(e)}'
        }), 500

# 路由: 暂停定时任务
@app.route('/api/scheduler/pause/<job_id>', methods=['POST'])
def pause_scheduler_job(job_id):
    try:
        job = scheduler.get_job(job_id)
        if not job:
            return jsonify({
                'status': 'error',
                'message': f'Job {job_id} not found'
            }), 404
        
        scheduler.pause_job(job_id)
        return jsonify({
            'status': 'ok',
            'message': f'Job {job_id} paused'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error pausing job: {str(e)}'
        }), 500

# 路由: 恢复定时任务
@app.route('/api/scheduler/resume/<job_id>', methods=['POST'])
def resume_scheduler_job(job_id):
    try:
        job = scheduler.get_job(job_id)
        if not job:
            return jsonify({
                'status': 'error',
                'message': f'Job {job_id} not found'
            }), 404
        
        scheduler.resume_job(job_id)
        return jsonify({
            'status': 'ok',
            'message': f'Job {job_id} resumed'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error resuming job: {str(e)}'
        }), 500

# 路由: 删除定时任务
@app.route('/api/scheduler/remove/<job_id>', methods=['POST'])
def remove_scheduler_job(job_id):
    try:
        job = scheduler.get_job(job_id)
        if not job:
            return jsonify({
                'status': 'error',
                'message': f'Job {job_id} not found'
            }), 404
        
        scheduler.remove_job(job_id)
        return jsonify({
            'status': 'ok',
            'message': f'Job {job_id} removed'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error removing job: {str(e)}'
        }), 500

# 定时执行工作流函数
def run_scheduled_workflow(workflow_id_prefix=None):
    """
    定时执行完整工作流的函数
    
    Args:
        workflow_id_prefix: 工作流ID前缀，用于标识特定的调度任务
    """
    # 生成工作流ID
    if workflow_id_prefix:
        workflow_id = f"{workflow_id_prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    else:
        workflow_id = f"scheduled_workflow_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # 确保不超过50个字符
    if len(workflow_id) > 50:
        workflow_id = workflow_id[:50]
    
    logger.info(f"开始执行定时工作流: {workflow_id}")
    
    try:
        # 直接执行完整工作流
        result = workflow_manager.run_complete_extended_workflow()
        logger.info(f"定时工作流 {workflow_id} 执行完成")
        return result
    except Exception as e:
        error_msg = f"执行定时工作流 {workflow_id} 时出错: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return None

# 命令行入口点 - 直接运行
if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'run-workflow':
            # 直接运行工作流
            logger.info("开始运行完整工作流...")
            workflow_id, results = workflow_manager.run_complete_workflow()
            if results:
                logger.info(f"工作流 {workflow_id} 已完成")
                logger.info(f"有效链接: {len(results['valid'])}")
                logger.info(f"无效链接: {len(results['invalid'])}")
                logger.info(f"失败链接: {len(results['failed'])}")
            else:
                logger.info(f"工作流 {workflow_id} 未返回结果")
        elif sys.argv[1] == 'analyze-latest':
            # 运行最新链接分析
            logger.info("开始分析最新抓取的链接...")
            max_links = 50
            if len(sys.argv) > 2:
                try:
                    max_links = int(sys.argv[2])
                except ValueError:
                    pass
            workflow_id, results = workflow_manager.analyze_latest_links(max_links)
            if results:
                logger.info(f"最新链接分析 {workflow_id} 已完成")
                logger.info(f"有效链接: {len(results['valid'])}")
                logger.info(f"无效链接: {len(results['invalid'])}")
                logger.info(f"失败链接: {len(results['failed'])}")
                
                # 打印有效链接
                if results['valid']:
                    logger.info("\n有效链接:")
                    for i, link_info in enumerate(results['valid'][:50], start=1):
                        logger.info(f"{i}. {link_info['link']} (来源: {link_info['source']})")
                    if len(results['valid']) > 50:
                        logger.info(f"...还有 {len(results['valid'])-50} 个有效链接")
            else:
                logger.info(f"最新链接分析 {workflow_id} 未返回结果")
        elif sys.argv[1] == 'process-valid':
            # 运行步骤3分析
            logger.info("开始处理有效链接...")
            max_links = 50
            if len(sys.argv) > 2:
                try:
                    max_links = int(sys.argv[2])
                except ValueError:
                    pass
            workflow_id, results = workflow_manager.process_valid_links(max_links=max_links)
            if results:
                logger.info(f"有效链接处理 {workflow_id} 已完成")
                logger.info(f"成功分析: {sum(1 for r in results if r['success'])}")
                logger.info(f"失败分析: {sum(1 for r in results if not r['success'])}")
            else:
                logger.info(f"有效链接处理 {workflow_id} 未返回结果")
        elif sys.argv[1] == 'extended-workflow':
            # 运行完整扩展工作流
            logger.info("开始运行完整扩展工作流...")
            workflow_id, results = workflow_manager.run_complete_extended_workflow()
            if results:
                logger.info(f"扩展工作流 {workflow_id} 已完成")
                logger.info(f"步骤1找到的链接: {results['step1_links_found']}")
                logger.info(f"步骤2有效链接: {results['step2_valid_links']}")
                logger.info(f"步骤3成功分析: {sum(1 for r in results['step3_results'] if r['success'])}")
                logger.info(f"步骤3失败分析: {sum(1 for r in results['step3_results'] if not r['success'])}")
            else:
                logger.info(f"扩展工作流 {workflow_id} 未返回结果")
        elif sys.argv[1] == 'scheduler-status':
            # 打印调度器状态
            jobs = scheduler.get_jobs()
            logger.info(f"当前有 {len(jobs)} 个调度任务")
            for job in jobs:
                next_run = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else "未调度"
                logger.info(f"任务ID: {job.id}, 下次运行时间: {next_run}")
    else:
        # 启动API服务器
        logger.info("启动API服务器...")
        logger.info("启动调度器...")
        # 调度器已在应用程序启动时初始化
        app.run(host='0.0.0.0', port=5000, debug=False) 