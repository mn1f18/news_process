import psycopg2
import logging
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DBSetup")

# 数据库连接配置
PG_CONFIG = {
    'host': '47.86.227.107',
    'port': 5432,
    'user': 'postgres',
    'password': 'root_password',
    'dbname': 'postgres'  # 默认连接到postgres数据库
}

# 创建表格的SQL语句
CREATE_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS step0_workflows (
        workflow_id VARCHAR(50) PRIMARY KEY,
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL,
        current_status VARCHAR(20) NOT NULL,
        details JSONB
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS step0_workflow_history (
        id SERIAL PRIMARY KEY,
        workflow_id VARCHAR(50) REFERENCES step0_workflows(workflow_id),
        status VARCHAR(20) NOT NULL,
        timestamp TIMESTAMP NOT NULL,
        details JSONB,
        error TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS step1_link_cache (
        homepage_url TEXT NOT NULL,
        link TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL,
        PRIMARY KEY (homepage_url, link)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS step1_new_links (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMP NOT NULL,
        homepage_url TEXT NOT NULL,
        link TEXT NOT NULL,
        source TEXT,
        note TEXT,
        batch_id VARCHAR(50) NOT NULL,
        created_at TIMESTAMP NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS step2_link_analysis (
        link_id VARCHAR(50) PRIMARY KEY,
        link TEXT NOT NULL,
        is_valid BOOLEAN NOT NULL,
        analysis_result JSONB,
        confidence FLOAT,
        reason TEXT,
        workflow_id VARCHAR(50) REFERENCES step0_workflows(workflow_id),
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS step2_analysis_results (
        id SERIAL PRIMARY KEY,
        workflow_id VARCHAR(50) REFERENCES step0_workflows(workflow_id),
        batch_id VARCHAR(50) NOT NULL,
        analysis_data JSONB NOT NULL,
        created_at TIMESTAMP NOT NULL
    );
    """
]

# 创建索引的SQL语句
CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_step1_new_links_batch_id ON step1_new_links(batch_id);",
    "CREATE INDEX IF NOT EXISTS idx_step2_link_analysis_workflow_id ON step2_link_analysis(workflow_id);",
    "CREATE INDEX IF NOT EXISTS idx_step2_analysis_results_workflow_id ON step2_analysis_results(workflow_id);"
]

def create_tables():
    """创建PostgreSQL表格"""
    conn = None
    try:
        # 连接到PostgreSQL
        logger.info("正在连接到PostgreSQL...")
        conn = psycopg2.connect(**PG_CONFIG)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # 创建表格
        logger.info("开始创建表格...")
        for sql in CREATE_TABLES_SQL:
            cursor.execute(sql)
            logger.info(f"已执行SQL: {sql.strip().split('(')[0]}")
        
        # 创建索引
        logger.info("开始创建索引...")
        for sql in CREATE_INDEXES_SQL:
            cursor.execute(sql)
            logger.info(f"已执行SQL: {sql}")
        
        logger.info("所有PostgreSQL表格和索引创建完成！")
        
    except Exception as e:
        logger.error(f"创建表格失败: {str(e)}")
    finally:
        if conn:
            conn.close()
            logger.info("PostgreSQL连接已关闭")

if __name__ == "__main__":
    create_tables() 