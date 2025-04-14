import os
import json
import logging
import time
from datetime import datetime
import uuid
import pandas as pd
from flask import Flask, request, jsonify
import threading
import queue
import traceback

# 导入我们的组件
from step_1_homepage_scrape import HomepageScraper
from step2_link_test import LinkAnalyzer
from step_3_scrape_test_sdk import sdk_call

# 配置日志系统
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
log_file = os.path.join(log_dir, f"app_{datetime.now().strftime('%Y%m%d')}.log")

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()  # 同时输出到控制台
    ]
)
logger = logging.getLogger("NewsApp")

# 创建Flask应用
app = Flask(__name__)
# 设置JSON编码，不转义中文字符
app.config['JSON_AS_ASCII'] = False

# 创建目录结构
data_dir = "data"
data_structure = {
    "step1": ["archives"],
    "step2": ["analysis_results"],
    "step3": ["content", "summaries"],
    "workflow": []
}

# 确保数据目录结构存在
for main_dir, sub_dirs in data_structure.items():
    main_path = os.path.join(data_dir, main_dir)
    if not os.path.exists(main_path):
        os.makedirs(main_path)
    
    for sub_dir in sub_dirs:
        sub_path = os.path.join(main_path, sub_dir)
        if not os.path.exists(sub_path):
            os.makedirs(sub_path)

# 定义文件路径
STEP1 = {
    "link_cache": os.path.join(data_dir, "step1", "link_cache.json"),
    "new_links": os.path.join(data_dir, "step1", "new_links.json"),
    "archives": os.path.join(data_dir, "step1", "archives")
}

STEP2 = {
    "valid_links": os.path.join(data_dir, "step2", "valid_links.json"),
    "invalid_links": os.path.join(data_dir, "step2", "invalid_links.json"),
    "analysis_results": os.path.join(data_dir, "step2", "analysis_results")
}

STEP3 = {
    "content": os.path.join(data_dir, "step3", "content"),
    "summaries": os.path.join(data_dir, "step3", "summaries")
}

WORKFLOW = {
    "status": os.path.join(data_dir, "workflow", "status.json")
}

# 确保状态文件存在
if not os.path.exists(WORKFLOW["status"]):
    with open(WORKFLOW["status"], 'w', encoding='utf-8') as f:
        json.dump({}, f, ensure_ascii=False, indent=2)

# 任务队列
task_queue = queue.Queue()

class WorkflowManager:
    """工作流管理器，负责协调三个步骤之间的工作流"""
    
    def __init__(self):
        # 初始化组件，使用新的文件路径
        self.homepage_scraper = HomepageScraper(
            "testhomepage.xlsx", 
            cache_file=STEP1["link_cache"],
            new_links_file=STEP1["new_links"],
            archive_dir=STEP1["archives"]
        )
        
        # 初始化链接分析器，使用新的文件路径
        self.link_analyzer = LinkAnalyzer(
            valid_links_file=STEP2["valid_links"],
            invalid_links_file=STEP2["invalid_links"]
        )
        
    def update_workflow_status(self, workflow_id, status, details=None, error=None):
        """更新工作流状态"""
        try:
            status_data = {}
            if os.path.exists(WORKFLOW["status"]):
                with open(WORKFLOW["status"], 'r', encoding='utf-8') as f:
                    status_data = json.load(f)
            
            # 更新状态
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if workflow_id not in status_data:
                status_data[workflow_id] = {
                    'created_at': timestamp,
                    'history': []
                }
            
            # 添加新状态记录
            new_status = {
                'status': status,
                'timestamp': timestamp
            }
            
            if details:
                new_status['details'] = details
            
            if error:
                new_status['error'] = error
            
            status_data[workflow_id]['history'].append(new_status)
            status_data[workflow_id]['current_status'] = status
            status_data[workflow_id]['updated_at'] = timestamp
            
            # 保存状态数据
            with open(WORKFLOW["status"], 'w', encoding='utf-8') as f:
                json.dump(status_data, f, ensure_ascii=False, indent=2)
                
            logger.debug(f"工作流 {workflow_id} 状态已更新为 {status}")
            
        except Exception as e:
            logger.error(f"更新工作流状态时出错: {e}")
    
    def get_workflow_status(self, workflow_id):
        """获取工作流状态"""
        try:
            if os.path.exists(WORKFLOW["status"]):
                with open(WORKFLOW["status"], 'r', encoding='utf-8') as f:
                    status_data = json.load(f)
                
                if workflow_id in status_data:
                    return status_data[workflow_id]
            
            return None
        except Exception as e:
            logger.error(f"获取工作流状态时出错: {e}")
            return None
    
    def get_all_workflow_status(self, status_filter=None):
        """获取所有工作流状态，可选按状态筛选"""
        try:
            if os.path.exists(WORKFLOW["status"]):
                with open(WORKFLOW["status"], 'r', encoding='utf-8') as f:
                    status_data = json.load(f)
                
                if status_filter:
                    return {k: v for k, v in status_data.items() 
                            if v.get('current_status') == status_filter}
                return status_data
            
            return {}
        except Exception as e:
            logger.error(f"获取所有工作流状态时出错: {e}")
            return {}
    
    def start_homepage_scraping(self, workflow_id=None):
        """启动主页抓取流程"""
        if workflow_id is None:
            workflow_id = f"workflow_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
        try:
            # 更新工作流状态
            self.update_workflow_status(workflow_id, "SCRAPING_STARTED")
            
            # 运行主页抓取
            logger.info(f"开始主页抓取，工作流ID: {workflow_id}")
            self.homepage_scraper.check_for_new_links()
            
            # 获取新发现的链接
            new_links_data = self.get_newly_discovered_links()
            
            if not new_links_data:
                logger.info("没有发现新链接，工作流完成")
                self.update_workflow_status(workflow_id, "COMPLETED", 
                                            details={"message": "没有发现新链接"})
                return workflow_id, []
            
            # 从新链接数据中提取链接
            all_links = []
            for timestamp, sites in new_links_data.items():
                for site, data in sites.items():
                    # 使用site作为分类标签
                    for link in data.get('new_links', []):
                        all_links.append({
                            'link': link,
                            'source': data.get('source', ''),
                            'note': data.get('note', ''),
                            'homepage': site,
                            'batch_id': data.get('batch_id', '')
                        })
            
            # 更新工作流状态
            self.update_workflow_status(workflow_id, "SCRAPING_COMPLETED", 
                                       details={"links_found": len(all_links)})
            
            logger.info(f"主页抓取完成，发现 {len(all_links)} 个新链接")
            return workflow_id, all_links
            
        except Exception as e:
            error_msg = f"主页抓取过程出错: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.update_workflow_status(workflow_id, "SCRAPING_FAILED", error=error_msg)
            return workflow_id, []
    
    def get_newly_discovered_links(self):
        """从step1/new_links.json文件中获取新发现的链接"""
        try:
            if os.path.exists(STEP1["new_links"]):
                with open(STEP1["new_links"], 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"获取新链接数据时出错: {e}")
            return {}

    def get_latest_links(self, max_links=50):
        """获取最新的一批链接，用于分析"""
        try:
            # 读取所有新链接
            new_links_data = self.get_newly_discovered_links()
            if not new_links_data:
                logger.warning("没有找到任何新链接数据")
                return []
            
            # 按时间戳排序，获取最新的条目
            timestamps = sorted(new_links_data.keys(), reverse=True)
            if not timestamps:
                return []
            
            # 获取最新的时间戳
            latest_timestamp = timestamps[0]
            latest_data = new_links_data[latest_timestamp]
            
            # 收集所有链接
            all_links = []
            for site, data in latest_data.items():
                for link in data.get('new_links', []):
                    all_links.append({
                        'link': link,
                        'source': data.get('source', ''),
                        'note': data.get('note', ''),
                        'homepage': site,
                        'batch_id': data.get('batch_id', '')
                    })
                    if len(all_links) >= max_links:
                        break
                if len(all_links) >= max_links:
                    break
            
            logger.info(f"获取到最新的 {len(all_links)} 个链接用于分析，时间戳: {latest_timestamp}")
            return all_links
            
        except Exception as e:
            error_msg = f"获取最新链接时出错: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            return []
    
    def analyze_links(self, links, workflow_id):
        """分析链接列表，确定哪些需要爬取"""
        try:
            # 更新工作流状态
            self.update_workflow_status(workflow_id, "ANALYSIS_STARTED", 
                                       details={"links_count": len(links)})
            
            # 提取纯链接列表
            pure_links = [item['link'] for item in links]
            
            # 分析链接
            logger.info(f"开始分析 {len(pure_links)} 个链接，工作流ID: {workflow_id}")
            analysis_results = self.link_analyzer.process_links(pure_links)
            
            # 将分析结果与原始链接信息合并
            enriched_results = {
                'batch_id': analysis_results['batch_id'],
                'workflow_id': workflow_id,
                'valid': [],
                'invalid': [],
                'failed': []
            }
            
            # 处理有效链接
            for link in analysis_results['valid']:
                # 找到原始链接信息
                original_info = next((item for item in links if item['link'] == link), {})
                # 合并信息
                link_info = original_info.copy()
                link_info['link_id'] = analysis_results['link_ids'].get(link)
                enriched_results['valid'].append(link_info)
            
            # 处理无效链接
            for link in analysis_results['invalid']:
                original_info = next((item for item in links if item['link'] == link), {})
                link_info = original_info.copy()
                link_info['link_id'] = analysis_results['link_ids'].get(link)
                enriched_results['invalid'].append(link_info)
            
            # 处理失败链接
            for link in analysis_results['failed']:
                original_info = next((item for item in links if item['link'] == link), {})
                link_info = original_info.copy()
                link_info['link_id'] = analysis_results['link_ids'].get(link)
                enriched_results['failed'].append(link_info)
            
            # 保存分析结果
            self.save_analysis_results(enriched_results, workflow_id)
            
            # 更新工作流状态
            self.update_workflow_status(workflow_id, "ANALYSIS_COMPLETED", 
                                       details={
                                           "valid_count": len(enriched_results['valid']),
                                           "invalid_count": len(enriched_results['invalid']),
                                           "failed_count": len(enriched_results['failed'])
                                       })
            
            logger.info(f"链接分析完成，工作流ID: {workflow_id}")
            logger.info(f"有效链接: {len(enriched_results['valid'])}, "
                       f"无效链接: {len(enriched_results['invalid'])}, "
                       f"失败链接: {len(enriched_results['failed'])}")
            
            return enriched_results
            
        except Exception as e:
            error_msg = f"链接分析过程出错: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.update_workflow_status(workflow_id, "ANALYSIS_FAILED", error=error_msg)
            return None
    
    def save_analysis_results(self, results, workflow_id):
        """保存分析结果到step2/analysis_results目录"""
        try:
            # 创建文件名
            results_file = os.path.join(STEP2["analysis_results"], f"analysis_{workflow_id}.json")
            
            # 保存数据
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
                
            logger.info(f"分析结果已保存到 {results_file}")
            
        except Exception as e:
            logger.error(f"保存分析结果时出错: {e}")

    def analyze_latest_links(self, max_links=50):
        """单独分析最新抓取的链接"""
        # 生成工作流ID
        workflow_id = f"workflow_latest_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        try:
            # 更新工作流状态
            logger.info(f"启动最新链接分析，ID: {workflow_id}")
            self.update_workflow_status(workflow_id, "LATEST_ANALYSIS_STARTED")
            
            # 获取最新链接
            latest_links = self.get_latest_links(max_links)
            
            if not latest_links:
                logger.info("没有找到最新链接，工作流结束")
                self.update_workflow_status(workflow_id, "LATEST_ANALYSIS_COMPLETED", 
                                           details={"message": "没有找到最新链接"})
                return workflow_id, None
            
            # 链接分析
            analysis_results = self.analyze_links(latest_links, workflow_id)
            
            # 更新工作流状态
            self.update_workflow_status(workflow_id, "LATEST_ANALYSIS_COMPLETED")
            
            logger.info(f"最新链接分析已完成，ID: {workflow_id}")
            return workflow_id, analysis_results
            
        except Exception as e:
            error_msg = f"最新链接分析出错: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.update_workflow_status(workflow_id, "LATEST_ANALYSIS_FAILED", error=error_msg)
            return workflow_id, None
    
    def run_complete_workflow(self):
        """运行完整的工作流程：抓取 -> 分析"""
        # 生成工作流ID
        workflow_id = f"workflow_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        try:
            # 第一步：主页抓取
            logger.info(f"启动完整工作流，ID: {workflow_id}")
            self.update_workflow_status(workflow_id, "WORKFLOW_STARTED")
            
            _, links = self.start_homepage_scraping(workflow_id)
            
            if not links:
                logger.info("没有新链接，工作流结束")
                self.update_workflow_status(workflow_id, "WORKFLOW_COMPLETED", 
                                           details={"message": "没有新链接需要处理"})
                return workflow_id, None
            
            # 第二步：链接分析
            analysis_results = self.analyze_links(links, workflow_id)
            
            # 更新工作流状态
            self.update_workflow_status(workflow_id, "WORKFLOW_COMPLETED")
            
            logger.info(f"完整工作流已完成，ID: {workflow_id}")
            return workflow_id, analysis_results
            
        except Exception as e:
            error_msg = f"工作流执行出错: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.update_workflow_status(workflow_id, "WORKFLOW_FAILED", error=error_msg)
            return workflow_id, None

    def process_valid_links(self, workflow_id=None, input_links=None, max_links=10):
        """处理步骤2筛选出的有效链接，传递给步骤3进行深度分析
        
        参数:
            workflow_id: 工作流ID，如果为None则自动生成
            input_links: 指定的有效链接列表，如果为None则从最近分析结果中获取
            max_links: 最多处理的链接数量
        """
        if workflow_id is None:
            workflow_id = f"workflow_step3_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        try:
            # 更新工作流状态
            logger.info(f"启动有效链接深度分析，ID: {workflow_id}")
            self.update_workflow_status(workflow_id, "STEP3_ANALYSIS_STARTED")
            
            # 获取有效链接
            valid_links = []
            
            if input_links:
                # 使用指定的链接
                valid_links = input_links[:max_links]
                logger.info(f"使用指定的 {len(valid_links)} 个链接进行深度分析")
            else:
                # 从最近的分析结果中获取有效链接
                analysis_files = [f for f in os.listdir(STEP2["analysis_results"]) if f.startswith("analysis_workflow_")]
                if not analysis_files:
                    logger.warning("没有找到分析结果文件")
                    self.update_workflow_status(workflow_id, "STEP3_ANALYSIS_COMPLETED", 
                                            details={"message": "没有找到分析结果文件"})
                    return workflow_id, []
                
                # 按文件修改时间排序，获取最新的分析结果
                latest_file = sorted(analysis_files, key=lambda x: os.path.getmtime(os.path.join(STEP2["analysis_results"], x)), reverse=True)[0]
                latest_file_path = os.path.join(STEP2["analysis_results"], latest_file)
                
                with open(latest_file_path, 'r', encoding='utf-8') as f:
                    analysis_results = json.load(f)
                
                if 'valid' not in analysis_results or not analysis_results['valid']:
                    logger.warning(f"在分析结果 {latest_file} 中没有找到有效链接")
                    self.update_workflow_status(workflow_id, "STEP3_ANALYSIS_COMPLETED", 
                                            details={"message": "没有找到有效链接"})
                    return workflow_id, []
                
                # 提取有效链接
                valid_links = [link_info['link'] for link_info in analysis_results['valid'][:max_links]]
                logger.info(f"从最新分析结果 {latest_file} 中获取了 {len(valid_links)} 个有效链接")
            
            if not valid_links:
                logger.warning("没有找到有效链接，步骤3分析结束")
                self.update_workflow_status(workflow_id, "STEP3_ANALYSIS_COMPLETED", 
                                         details={"message": "没有有效链接"})
                return workflow_id, []
            
            # 调用步骤3进行深度分析
            logger.info(f"开始对 {len(valid_links)} 个有效链接进行步骤3分析")
            
            step3_results = []
            for i, link in enumerate(valid_links, 1):
                logger.info(f"步骤3分析链接 [{i}/{len(valid_links)}]: {link}")
                
                try:
                    # 调用步骤3的SDK函数
                    result = sdk_call(link)
                    
                    if result:
                        # 保存结果到步骤3内容目录
                        result_file = os.path.join(STEP3["content"], f"link_{workflow_id}_{i}.txt")
                        with open(result_file, 'w', encoding='utf-8') as f:
                            # 添加链接ID到结果中
                            result_dict = json.loads(result)
                            result_dict['link_id'] = f"{workflow_id}_{i}"
                            f.write(json.dumps(result_dict, ensure_ascii=False, indent=2))
                        
                        step3_results.append({
                            "link": link,
                            "success": True,
                            "result_file": result_file,
                            "link_id": f"{workflow_id}_{i}"
                        })
                        logger.info(f"链接分析成功，结果已保存到 {result_file}")
                    else:
                        step3_results.append({
                            "link": link,
                            "success": False,
                            "error": "没有获取到响应"
                        })
                        logger.warning(f"链接分析失败，没有获取到响应")
                except Exception as e:
                    error_msg = f"分析链接时出错: {str(e)}"
                    logger.error(error_msg)
                    step3_results.append({
                        "link": link,
                        "success": False,
                        "error": error_msg
                    })
            
            # 保存整体分析结果到步骤3摘要目录
            summary_file = os.path.join(STEP3["summaries"], f"summary_{workflow_id}.json")
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "workflow_id": workflow_id,
                    "total_links": len(valid_links),
                    "successful_analysis": sum(1 for r in step3_results if r["success"]),
                    "failed_analysis": sum(1 for r in step3_results if not r["success"]),
                    "results": step3_results
                }, f, ensure_ascii=False, indent=2)
            
            # 更新工作流状态
            self.update_workflow_status(workflow_id, "STEP3_ANALYSIS_COMPLETED", 
                                     details={
                                         "total_links": len(valid_links),
                                         "successful_analysis": sum(1 for r in step3_results if r["success"]),
                                         "failed_analysis": sum(1 for r in step3_results if not r["success"])
                                     })
            
            logger.info(f"步骤3分析完成，分析了 {len(valid_links)} 个链接，其中 {sum(1 for r in step3_results if r['success'])} 个成功，{sum(1 for r in step3_results if not r['success'])} 个失败")
            logger.info(f"分析摘要已保存到 {summary_file}")
            
            return workflow_id, step3_results
        
        except Exception as e:
            error_msg = f"步骤3分析出错: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.update_workflow_status(workflow_id, "STEP3_ANALYSIS_FAILED", error=error_msg)
            return workflow_id, []

    def run_complete_extended_workflow(self):
        """运行完整的扩展工作流程：抓取 -> 分析 -> 深度分析"""
        # 生成工作流ID
        workflow_id = f"workflow_extended_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        try:
            # 第一步：主页抓取
            logger.info(f"启动完整扩展工作流，ID: {workflow_id}")
            self.update_workflow_status(workflow_id, "EXTENDED_WORKFLOW_STARTED")
            
            _, links = self.start_homepage_scraping(workflow_id)
            
            if not links:
                logger.info("没有新链接，工作流结束")
                self.update_workflow_status(workflow_id, "EXTENDED_WORKFLOW_COMPLETED", 
                                           details={"message": "没有新链接需要处理"})
                return workflow_id, None
            
            # 第二步：链接分析
            analysis_results = self.analyze_links(links, workflow_id)
            
            if not analysis_results or not analysis_results.get('valid'):
                logger.info("没有有效链接，工作流结束")
                self.update_workflow_status(workflow_id, "EXTENDED_WORKFLOW_COMPLETED", 
                                           details={"message": "没有有效链接需要深度分析"})
                return workflow_id, None
            
            # 第三步：深度分析有效链接
            valid_links = [link_info['link'] for link_info in analysis_results['valid']]
            _, step3_results = self.process_valid_links(workflow_id, valid_links)
            
            # 更新工作流状态
            self.update_workflow_status(workflow_id, "EXTENDED_WORKFLOW_COMPLETED")
            
            logger.info(f"完整扩展工作流已完成，ID: {workflow_id}")
            return workflow_id, {
                "step1_links_found": len(links),
                "step2_valid_links": len(analysis_results['valid']),
                "step3_results": step3_results
            }
            
        except Exception as e:
            error_msg = f"扩展工作流执行出错: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.update_workflow_status(workflow_id, "EXTENDED_WORKFLOW_FAILED", error=error_msg)
            return workflow_id, None

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
                    task.get('max_links', 10)
                )
            elif task['type'] == 'extended_workflow':
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
    
    workflow_id = f"workflow_step2_latest_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
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
    max_links = data.get('max_links', 10)
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
        'message': 'Complete workflow (step1-2) has been queued'
    })

# 路由: 完整工作流（步骤1+2+3）
@app.route('/api/workflow/all', methods=['POST'])
def all_workflow():
    workflow_id = f"workflow_all_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # 将任务添加到队列
    task_queue.put({
        'type': 'extended_workflow',
        'workflow_id': workflow_id
    })
    
    return jsonify({
        'status': 'accepted',
        'workflow_id': workflow_id,
        'message': 'Extended workflow (step1-2-3) has been queued'
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
    # 首先在有效链接中查找
    valid_links = {}
    if os.path.exists(STEP2["valid_links"]):
        with open(STEP2["valid_links"], 'r', encoding='utf-8') as f:
            valid_links = json.load(f)
    
    if link_id in valid_links:
        return jsonify({
            'status': 'ok',
            'link_id': link_id,
            'data': valid_links[link_id],
            'type': 'valid'
        })
    
    # 再在无效链接中查找
    invalid_links = {}
    if os.path.exists(STEP2["invalid_links"]):
        with open(STEP2["invalid_links"], 'r', encoding='utf-8') as f:
            invalid_links = json.load(f)
    
    if link_id in invalid_links:
        return jsonify({
            'status': 'ok',
            'link_id': link_id,
            'data': invalid_links[link_id],
            'type': 'invalid'
        })
    
    # 找不到链接
    return jsonify({
        'status': 'error',
        'message': f'Link {link_id} not found'
    }), 404

# 路由: 重新分析失败的链接
@app.route('/api/reanalyze', methods=['POST'])
def reanalyze_failed_links():
    workflow_id = f"workflow_reanalyze_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # 从两个文件中获取所有链接
    valid_links = {}
    invalid_links = {}
    
    if os.path.exists(STEP2["valid_links"]):
        with open(STEP2["valid_links"], 'r', encoding='utf-8') as f:
            valid_links = json.load(f)
    
    if os.path.exists(STEP2["invalid_links"]):
        with open(STEP2["invalid_links"], 'r', encoding='utf-8') as f:
            invalid_links = json.load(f)
    
    # 查找状态为FAILED的链接
    failed_links = []
    for link_id, data in {**valid_links, **invalid_links}.items():
        if data.get('current_status') == "FAILED":
            failed_links.append(data.get('link'))
    
    if not failed_links:
        return jsonify({
            'status': 'ok',
            'message': 'No failed links to reanalyze'
        })
    
    # 更新工作流状态
    workflow_manager.update_workflow_status(workflow_id, "REANALYSIS_STARTED", 
                                          details={"failed_links_count": len(failed_links)})
    
    # 重新分析失败的链接
    link_analyzer = LinkAnalyzer(
        valid_links_file=STEP2["valid_links"],
        invalid_links_file=STEP2["invalid_links"]
    )
    result = link_analyzer.process_links(failed_links)
    
    # 更新工作流状态
    workflow_manager.update_workflow_status(workflow_id, "REANALYSIS_COMPLETED", 
                                          details={"reanalyzed_count": len(result.get('valid', [])) + len(result.get('invalid', []))})
    
    return jsonify({
        'status': 'ok',
        'workflow_id': workflow_id,
        'reanalyzed_count': len(result.get('valid', [])) + len(result.get('invalid', [])),
        'message': f'Successfully reanalyzed {len(result.get("valid", [])) + len(result.get("invalid", []))} failed links'
    })

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
                    for i, link_info in enumerate(results['valid'][:10], start=1):
                        logger.info(f"{i}. {link_info['link']} (来源: {link_info['source']})")
                    if len(results['valid']) > 10:
                        logger.info(f"...还有 {len(results['valid'])-10} 个有效链接")
            else:
                logger.info(f"最新链接分析 {workflow_id} 未返回结果")
        elif sys.argv[1] == 'process-valid':
            # 运行步骤3分析
            logger.info("开始处理有效链接...")
            max_links = 10
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
    else:
        # 启动API服务器
        logger.info("启动API服务器...")
        app.run(host='0.0.0.0', port=5000, debug=True) 