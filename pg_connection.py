import logging
import time
import traceback
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from config import PG_CONFIG

# 创建日志记录器
logger = logging.getLogger(__name__)

# 全局连接池
PG_POOL = None

def init_pg_pool():
    """初始化PostgreSQL连接池"""
    global PG_POOL
    try:
        if PG_POOL is not None:
            # 如果已存在连接池，先尝试关闭
            try:
                PG_POOL.closeall()
            except Exception as e:
                logger.error(f"关闭现有PostgreSQL连接池失败: {str(e)}")
            PG_POOL = None
            
        # 创建新的连接池
        PG_POOL = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            host=PG_CONFIG['host'],
            port=PG_CONFIG['port'],
            database=PG_CONFIG['database'],
            user=PG_CONFIG['user'],
            password=PG_CONFIG['password']
        )
        logger.info("PostgreSQL连接池初始化成功")
    except Exception as e:
        logger.error(f"初始化PostgreSQL连接池失败: {str(e)}")
        logger.error(traceback.format_exc())
        PG_POOL = None
        raise

class pg_connection:
    """PostgreSQL 连接上下文管理器"""
    def __init__(self, max_retries=3):
        self.max_retries = max_retries
        self.retry_count = 0
        self.conn = None
        self.cursor = None
    
    def __enter__(self):
        global PG_POOL
        
        while self.retry_count < self.max_retries:
            try:
                if PG_POOL is None:
                    init_pg_pool()
                    if PG_POOL is None:
                        raise Exception("无法初始化PostgreSQL连接池")
                
                self.conn = PG_POOL.getconn()
                if self.conn is None:
                    raise Exception("无法从PostgreSQL连接池获取连接")
                    
                self.conn.autocommit = False
                self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
                return self.cursor
                
            except (psycopg2.pool.PoolError, psycopg2.InterfaceError) as e:
                self.retry_count += 1
                logger.warning(f"PostgreSQL连接池错误，正在重试 ({self.retry_count}/{self.max_retries}): {str(e)}")
                
                # 重新初始化连接池
                if self.retry_count < self.max_retries:
                    try:
                        # 确保关闭之前的连接
                        if self.cursor is not None:
                            try:
                                self.cursor.close()
                            except Exception:
                                pass
                            self.cursor = None
                            
                        if self.conn is not None:
                            try:
                                # 归还连接到连接池
                                PG_POOL.putconn(self.conn)
                            except Exception:
                                # 如果无法归还，尝试直接关闭
                                try:
                                    self.conn.close()
                                except Exception:
                                    pass
                            self.conn = None
                        
                        # 尝试重新初始化连接池
                        init_pg_pool()
                        time.sleep(1)  # 短暂暂停，避免立即重试
                    except Exception as init_error:
                        logger.error(f"重新初始化PostgreSQL连接池失败: {str(init_error)}")
                else:
                    logger.error("PostgreSQL连接重试失败，已达到最大重试次数")
                    raise
            except Exception as e:
                logger.error(f"获取PostgreSQL连接失败: {str(e)}")
                logger.error(traceback.format_exc())
                self.retry_count += 1
                if self.retry_count >= self.max_retries:
                    raise
                time.sleep(1)  # 短暂暂停，避免立即重试
                
        # 如果所有重试都失败，抛出异常
        if self.retry_count >= self.max_retries:
            raise Exception(f"PostgreSQL连接失败，已达到最大重试次数 ({self.max_retries})")
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        global PG_POOL
        
        if not hasattr(self, 'conn') or self.conn is None:
            return
            
        try:
            if exc_type is not None:
                logger.error(f"PostgreSQL操作出错: {str(exc_val)}")
                logger.error(traceback.format_exc())
                try:
                    self.conn.rollback()
                except Exception as e:
                    logger.error(f"回滚PostgreSQL事务失败: {str(e)}")
            else:
                try:
                    self.conn.commit()
                except Exception as e:
                    logger.error(f"提交PostgreSQL事务失败: {str(e)}")
                    try:
                        self.conn.rollback()
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"处理PostgreSQL事务时出错: {str(e)}")
            
        try:
            if hasattr(self, 'cursor') and self.cursor is not None:
                self.cursor.close()
                self.cursor = None
        except Exception as e:
            logger.error(f"关闭PostgreSQL游标时出错: {str(e)}")
            
        try:
            if self.conn is not None and PG_POOL is not None:
                PG_POOL.putconn(self.conn)
                self.conn = None
        except Exception as e:
            logger.error(f"归还PostgreSQL连接到连接池失败: {str(e)}")
            # 如果无法归还连接池，尝试直接关闭连接
            try:
                if self.conn is not None:
                    self.conn.close()
                    self.conn = None
            except Exception:
                pass

# 初始化全局连接池
if PG_POOL is None:
    try:
        init_pg_pool()
    except Exception as e:
        logger.error(f"初始化PostgreSQL连接池失败: {str(e)}") 