import mysql.connector
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DBSetup")

# MySQL数据库连接配置
MYSQL_CONFIG = {
    'host': '47.86.227.107',
    'port': 3306,
    'user': 'root',
    'password': 'root_password',
    'database': 'mysql'  # 先连接到默认数据库
}

# 创建数据库的SQL
CREATE_DATABASE_SQL = "CREATE DATABASE IF NOT EXISTS news_content"

# 删除旧表的SQL
DROP_OLD_TABLE_SQL = "DROP TABLE IF EXISTS step3_content"

# 创建表格的SQL
CREATE_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS step3_content (
        id INT AUTO_INCREMENT PRIMARY KEY,
        link_id VARCHAR(50) NOT NULL,
        title TEXT,
        content LONGTEXT,
        event_tags JSON,
        space_tags JSON,
        cat_tags JSON,
        publish_time DATE,
        importance VARCHAR(20),
        state JSON,
        source_note TEXT,
        homepage_url VARCHAR(255),
        workflow_id VARCHAR(50),
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY (link_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS homepage_urls (
        id INT AUTO_INCREMENT PRIMARY KEY,
        link VARCHAR(255) NOT NULL,
        source VARCHAR(100),
        note TEXT,
        active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY (link)
    )
    """
]

# 示例数据
SAMPLE_HOMEPAGE_DATA = [
    ("https://example.com/agriculture-news", "Example News", "Agriculture news site"),
    ("https://example.com/farming-policy", "Example Policy", "Farming policy site"),
    ("https://example.com/weather-impact", "Example Weather", "Weather impact on farming")
]

def create_tables():
    """创建MySQL数据库和表格"""
    conn = None
    try:
        # 连接到MySQL
        logger.info("正在连接到MySQL...")
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()
        
        # 创建数据库
        logger.info("正在创建数据库...")
        cursor.execute(CREATE_DATABASE_SQL)
        logger.info("数据库创建成功或已存在")
        
        # 切换到新数据库
        cursor.execute("USE news_content")
        logger.info("已切换到news_content数据库")
        
        # 删除旧的step3_content表
        logger.info("正在删除旧的step3_content表...")
        cursor.execute(DROP_OLD_TABLE_SQL)
        logger.info("旧表已删除或不存在")
        
        # 创建表格
        logger.info("正在创建表格...")
        for sql in CREATE_TABLES_SQL:
            cursor.execute(sql)
            logger.info(f"执行SQL: {sql.strip().split('(')[0]}")
        
        # 检查homepage_urls表是否有数据
        cursor.execute("SELECT COUNT(*) FROM homepage_urls")
        count = cursor.fetchone()[0]
        
        # 如果表是空的，插入示例数据
        if count == 0:
            logger.info("插入示例homepage_urls数据...")
            cursor.executemany(
                "INSERT INTO homepage_urls (link, source, note) VALUES (%s, %s, %s)",
                SAMPLE_HOMEPAGE_DATA
            )
            logger.info(f"插入了 {len(SAMPLE_HOMEPAGE_DATA)} 条示例数据")
        
        # 提交更改
        conn.commit()
        logger.info("所有MySQL表格创建完成！")
        
    except Exception as e:
        logger.error(f"创建表格失败: {str(e)}")
    finally:
        if conn:
            conn.close()
            logger.info("MySQL连接已关闭")

if __name__ == "__main__":
    create_tables() 