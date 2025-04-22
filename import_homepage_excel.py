import pandas as pd
import mysql.connector
import logging
from datetime import datetime
import config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ImportExcel")

def import_excel_to_db(excel_path):
    """从Excel文件导入homepage_urls数据到MySQL数据库"""
    try:
        # 读取Excel文件
        logger.info(f"从 {excel_path} 读取数据...")
        df = pd.read_excel(excel_path)
        
        # 确保必要的列存在
        if 'link' not in df.columns:
            logger.error("Excel文件中缺少'link'列")
            return False
        
        # 连接到MySQL数据库
        logger.info("连接到MySQL数据库...")
        conn = mysql.connector.connect(**config.MYSQL_CONFIG)
        cursor = conn.cursor()
        
        # 准备数据
        imported_count = 0
        for _, row in df.iterrows():
            try:
                link = row['link']
                source = row.get('来源', '') if '来源' in df.columns else ''
                note = row.get('备注', '') if '备注' in df.columns else ''
                
                # 检查链接是否已存在
                cursor.execute("SELECT id FROM homepage_urls WHERE link = %s", (link,))
                result = cursor.fetchone()
                
                if result:
                    # 更新现有记录
                    cursor.execute(
                        "UPDATE homepage_urls SET source = %s, note = %s WHERE link = %s",
                        (source, note, link)
                    )
                    logger.info(f"更新现有链接: {link}")
                else:
                    # 插入新记录
                    cursor.execute(
                        "INSERT INTO homepage_urls (link, source, note) VALUES (%s, %s, %s)",
                        (link, source, note)
                    )
                    logger.info(f"插入新链接: {link}")
                
                imported_count += 1
                
            except Exception as e:
                logger.error(f"处理行 {_} 时出错: {e}")
        
        # 提交事务
        conn.commit()
        logger.info(f"导入完成，成功导入 {imported_count} 条记录")
        
        # 关闭连接
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"导入Excel时出错: {e}")
        return False

if __name__ == "__main__":
    # 导入Excel文件
    import_excel_to_db("testhomepage.xlsx") 