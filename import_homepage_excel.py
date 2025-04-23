import pandas as pd
import mysql.connector
import config
import logging
from datetime import datetime
import os

# 配置日志系统
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
log_file = os.path.join(log_dir, f"import_excel_{datetime.now().strftime('%Y%m%d')}.log")

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()  # 同时输出到控制台
    ]
)
logger = logging.getLogger("ImportExcel")

def import_homepage_urls(excel_file):
    """从Excel文件导入主页URL到数据库"""
    try:
        # 读取Excel文件
        logger.info(f"开始读取Excel文件: {excel_file}")
        df = pd.read_excel(excel_file)
        
        # 验证必要的列是否存在
        required_columns = ['source', 'link', 'note']
        for col in required_columns:
            if col not in df.columns:
                raise ValueError(f"Excel文件缺少必要的列: {col}")
        
        # 连接到MySQL数据库
        logger.info("连接到MySQL数据库...")
        conn = mysql.connector.connect(**config.MYSQL_CONFIG)
        cursor = conn.cursor()
        
        # 准备SQL语句
        insert_sql = """
        INSERT INTO homepage_urls (source, link, note, active, created_at, updated_at)
        VALUES (%s, %s, %s, TRUE, NOW(), NOW())
        ON DUPLICATE KEY UPDATE
        source = VALUES(source),
        note = VALUES(note),
        active = TRUE,
        updated_at = NOW()
        """
        
        # 记录成功和失败的数量
        success_count = 0
        error_count = 0
        
        # 遍历DataFrame并插入数据
        for index, row in df.iterrows():
            try:
                # 准备数据
                source = str(row['source']).strip()
                link = str(row['link']).strip()
                note = str(row['note']).strip()
                
                # 执行插入
                cursor.execute(insert_sql, (source, link, note))
                success_count += 1
                logger.info(f"成功导入: {link}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"导入失败: {link}, 错误: {str(e)}")
        
        # 提交事务
        conn.commit()
        
        # 关闭连接
        cursor.close()
        conn.close()
        
        logger.info(f"导入完成: 成功 {success_count} 条, 失败 {error_count} 条")
        return True
        
    except Exception as e:
        logger.error(f"导入过程中出错: {str(e)}")
        return False

if __name__ == "__main__":
    # Excel文件路径
    excel_file = "testhomepage.xlsx"
    
    # 检查文件是否存在
    if not os.path.exists(excel_file):
        logger.error(f"Excel文件不存在: {excel_file}")
        exit(1)
    
    # 执行导入
    if import_homepage_urls(excel_file):
        logger.info("导入成功完成")
    else:
        logger.error("导入失败") 