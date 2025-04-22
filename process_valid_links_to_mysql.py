import os
import json
import logging
from datetime import datetime
import time
import traceback
from step_3_scrape_test_sdk import sdk_call
import db_utils

# 配置日志系统
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
log_file = os.path.join(log_dir, f"process_valid_links_{datetime.now().strftime('%Y%m%d')}.log")

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()  # 同时输出到控制台
    ]
)
logger = logging.getLogger("ProcessValidLinks")

def process_valid_links(max_links=10):
    """处理有效链接：从PostgreSQL读取，用SDK分析，保存到MySQL"""
    workflow_id = f"workflow_step3_db_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    try:
        # 更新工作流状态
        logger.info(f"启动有效链接深度分析，ID: {workflow_id}")
        db_utils.update_workflow_status(workflow_id, "STEP3_ANALYSIS_STARTED")
        
        # 从PostgreSQL获取有效链接
        valid_links = db_utils.get_valid_links(max_links)
        if not valid_links:
            logger.warning("没有找到有效链接，Step3分析结束")
            db_utils.update_workflow_status(workflow_id, "STEP3_ANALYSIS_COMPLETED", 
                                         details={"message": "没有有效链接"})
            return workflow_id, []
        
        logger.info(f"从PostgreSQL获取了 {len(valid_links)} 个有效链接")
        
        # 处理每个链接
        results = []
        for i, link_info in enumerate(valid_links, 1):
            logger.info(f"处理链接 [{i}/{len(valid_links)}]: {link_info['link']}")
            
            try:
                # 调用SDK分析链接
                result = sdk_call(link_info['link'])
                
                if result:
                    # 解析返回结果
                    result_dict = json.loads(result)
                    
                    # 保存到MySQL
                    success = db_utils.save_content(
                        link_info['link_id'],
                        result_dict.get('title', ''),
                        result_dict.get('content', ''),
                        result_dict.get('event_tags', []),
                        result_dict.get('space_tags', []),
                        result_dict.get('cat_tags', []),
                        result_dict.get('publish_time', ''),
                        result_dict.get('importance', '低'),
                        result_dict.get('state', ['爬取成功'])
                    )
                    
                    if success:
                        results.append({
                            "link_id": link_info['link_id'],
                            "link": link_info['link'],
                            "success": True
                        })
                        logger.info(f"链接 {link_info['link_id']} 分析结果已保存到MySQL")
                    else:
                        results.append({
                            "link_id": link_info['link_id'],
                            "link": link_info['link'],
                            "success": False,
                            "error": "保存到MySQL失败"
                        })
                        logger.error(f"链接 {link_info['link_id']} 分析结果保存失败")
                else:
                    results.append({
                        "link_id": link_info['link_id'],
                        "link": link_info['link'],
                        "success": False,
                        "error": "SDK调用返回为空"
                    })
                    logger.warning(f"链接 {link_info['link_id']} SDK调用返回为空")
            
            except Exception as e:
                error_msg = str(e)
                results.append({
                    "link_id": link_info['link_id'],
                    "link": link_info['link'],
                    "success": False,
                    "error": error_msg
                })
                logger.error(f"处理链接 {link_info['link_id']} 时出错: {error_msg}")
                logger.error(traceback.format_exc())
            
            # 每个链接处理完后暂停一下，避免过快请求
            if i < len(valid_links):
                time.sleep(2)
        
        # 更新工作流状态
        successful_count = sum(1 for r in results if r["success"])
        failed_count = sum(1 for r in results if not r["success"])
        
        db_utils.update_workflow_status(workflow_id, "STEP3_ANALYSIS_COMPLETED", 
                                     details={
                                         "total_links": len(valid_links),
                                         "successful_analysis": successful_count,
                                         "failed_analysis": failed_count
                                     })
        
        logger.info(f"处理完成：共 {len(valid_links)} 个链接，成功 {successful_count} 个，失败 {failed_count} 个")
        return workflow_id, results
        
    except Exception as e:
        error_msg = f"处理有效链接时出错: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        db_utils.update_workflow_status(workflow_id, "STEP3_ANALYSIS_FAILED", error=error_msg)
        return workflow_id, []

if __name__ == "__main__":
    import sys
    
    # 默认处理10个链接
    max_links = 10
    
    # 如果命令行指定了参数，则使用指定的数量
    if len(sys.argv) > 1:
        try:
            max_links = int(sys.argv[1])
        except ValueError:
            logger.warning(f"无效的链接数量参数: {sys.argv[1]}，使用默认值10")
    
    logger.info(f"开始处理最多 {max_links} 个有效链接")
    workflow_id, results = process_valid_links(max_links)
    
    logger.info(f"处理完成，工作流ID: {workflow_id}")
    if results:
        logger.info(f"成功处理: {sum(1 for r in results if r['success'])} 个链接")
        logger.info(f"处理失败: {sum(1 for r in results if not r['success'])} 个链接")
    else:
        logger.info("没有处理任何链接") 