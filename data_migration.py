import os
import json
import shutil
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DataMigration")

# 旧数据目录与文件
OLD_DATA = {
    "root": "data",
    "scrape_link_cache": "scrape_link_cache.json",
    "scrape_new_links": "scrape_new_links.json", 
    "archives": "archives",
    "valid_links": "data/valid_links.json",
    "invalid_links": "data/invalid_links.json",
    "analysis_results_prefix": "data/analysis_results_",
    "step3_results": "data/step3_results",
    "step3_summary_prefix": "data/step3_summary_",
    "workflow_status": "data/workflow_status.json"
}

# 新数据目录与文件
NEW_DATA = {
    "root": "data",
    "step1": {
        "dir": "data/step1",
        "link_cache": "data/step1/link_cache.json",
        "new_links": "data/step1/new_links.json",
        "archives": "data/step1/archives"
    },
    "step2": {
        "dir": "data/step2",
        "valid_links": "data/step2/valid_links.json",
        "invalid_links": "data/step2/invalid_links.json",
        "analysis_results": "data/step2/analysis_results"
    },
    "step3": {
        "dir": "data/step3",
        "content": "data/step3/content",
        "summaries": "data/step3/summaries"
    },
    "workflow": {
        "dir": "data/workflow",
        "status": "data/workflow/status.json"
    }
}

def ensure_dir_exists(dir_path):
    """确保目录存在"""
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        logger.info(f"创建目录: {dir_path}")

def copy_file(src, dst):
    """复制文件，确保目标目录存在"""
    if not os.path.exists(src):
        logger.warning(f"源文件不存在: {src}")
        return False
        
    ensure_dir_exists(os.path.dirname(dst))
    
    try:
        shutil.copy2(src, dst)
        logger.info(f"复制文件: {src} -> {dst}")
        return True
    except Exception as e:
        logger.error(f"复制文件失败: {src} -> {dst}, 错误: {e}")
        return False

def migrate_step1_data():
    """迁移步骤1的数据"""
    logger.info("开始迁移步骤1数据...")
    
    # 创建step1目录
    ensure_dir_exists(NEW_DATA["step1"]["dir"])
    
    # 迁移link_cache文件
    if os.path.exists(OLD_DATA["scrape_link_cache"]):
        copy_file(OLD_DATA["scrape_link_cache"], NEW_DATA["step1"]["link_cache"])
    
    # 迁移new_links文件
    if os.path.exists(OLD_DATA["scrape_new_links"]):
        copy_file(OLD_DATA["scrape_new_links"], NEW_DATA["step1"]["new_links"])
    
    # 迁移archives目录
    if os.path.exists(OLD_DATA["archives"]):
        ensure_dir_exists(NEW_DATA["step1"]["archives"])
        for item in os.listdir(OLD_DATA["archives"]):
            src = os.path.join(OLD_DATA["archives"], item)
            dst = os.path.join(NEW_DATA["step1"]["archives"], item)
            if os.path.isfile(src):
                copy_file(src, dst)
    
    logger.info("步骤1数据迁移完成")

def migrate_step2_data():
    """迁移步骤2的数据"""
    logger.info("开始迁移步骤2数据...")
    
    # 创建step2目录及子目录
    ensure_dir_exists(NEW_DATA["step2"]["dir"])
    ensure_dir_exists(NEW_DATA["step2"]["analysis_results"])
    
    # 迁移valid_links文件
    if os.path.exists(OLD_DATA["valid_links"]):
        copy_file(OLD_DATA["valid_links"], NEW_DATA["step2"]["valid_links"])
    
    # 迁移invalid_links文件
    if os.path.exists(OLD_DATA["invalid_links"]):
        copy_file(OLD_DATA["invalid_links"], NEW_DATA["step2"]["invalid_links"])
    
    # 迁移analysis_results文件
    for item in os.listdir(OLD_DATA["root"]):
        if item.startswith("analysis_results_"):
            src = os.path.join(OLD_DATA["root"], item)
            dst = os.path.join(NEW_DATA["step2"]["analysis_results"], item.replace("analysis_results_", "analysis_"))
            copy_file(src, dst)
    
    logger.info("步骤2数据迁移完成")

def migrate_step3_data():
    """迁移步骤3的数据"""
    logger.info("开始迁移步骤3数据...")
    
    # 创建step3目录及子目录
    ensure_dir_exists(NEW_DATA["step3"]["dir"])
    ensure_dir_exists(NEW_DATA["step3"]["content"])
    ensure_dir_exists(NEW_DATA["step3"]["summaries"])
    
    # 迁移step3_results目录内容
    if os.path.exists(OLD_DATA["step3_results"]):
        for item in os.listdir(OLD_DATA["step3_results"]):
            src = os.path.join(OLD_DATA["step3_results"], item)
            dst = os.path.join(NEW_DATA["step3"]["content"], item)
            if os.path.isfile(src):
                copy_file(src, dst)
    
    # 迁移step3_summary文件
    for item in os.listdir(OLD_DATA["root"]):
        if item.startswith("step3_summary_"):
            src = os.path.join(OLD_DATA["root"], item)
            dst = os.path.join(NEW_DATA["step3"]["summaries"], item.replace("step3_summary_", "summary_"))
            copy_file(src, dst)
    
    logger.info("步骤3数据迁移完成")

def migrate_workflow_data():
    """迁移工作流数据"""
    logger.info("开始迁移工作流数据...")
    
    # 创建workflow目录
    ensure_dir_exists(NEW_DATA["workflow"]["dir"])
    
    # 迁移workflow_status文件
    if os.path.exists(OLD_DATA["workflow_status"]):
        copy_file(OLD_DATA["workflow_status"], NEW_DATA["workflow"]["status"])
    
    logger.info("工作流数据迁移完成")

def run_migration():
    """运行完整的数据迁移"""
    logger.info("开始数据迁移...")
    
    # 备份旧数据目录
    backup_dir = f"data_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    logger.info(f"创建数据备份: {backup_dir}")
    
    if os.path.exists(OLD_DATA["root"]):
        shutil.copytree(OLD_DATA["root"], backup_dir)
        logger.info(f"旧数据已备份到: {backup_dir}")
    
    # 执行各步骤数据迁移
    migrate_step1_data()
    migrate_step2_data()
    migrate_step3_data()
    migrate_workflow_data()
    
    logger.info("数据迁移完成!")
    logger.info(f"旧数据备份位于: {backup_dir}")
    logger.info("如果迁移完全成功，可以删除备份数据")

if __name__ == "__main__":
    run_migration() 