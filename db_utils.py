import os
import json
import psycopg2
import psycopg2.extras
import traceback
import logging
import mysql.connector
from mysql.connector import pooling
from psycopg2 import pool
from config import PG_CONFIG, MYSQL_CONFIG
from datetime import datetime
import time
from logger_config import setup_logger

# 初始化日志记录器
logger = setup_logger("db_utils")

# 全局连接池
PG_POOL = None
MYSQL_POOL = None

def init_db_pools():
    """初始化数据库连接池"""
    global PG_POOL, MYSQL_POOL
    
    try:
        # 初始化 PostgreSQL 连接池
        PG_POOL = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            host=PG_CONFIG['host'],
            port=PG_CONFIG['port'],
            database=PG_CONFIG['database'],
            user=PG_CONFIG['user'],
            password=PG_CONFIG['password']
        )
        logger.info("PostgreSQL 连接池初始化成功")
    except Exception as e:
        logger.error(f"PostgreSQL 连接池初始化失败: {str(e)}")
        logger.error(traceback.format_exc())
        PG_POOL = None
    
    try:
        # 初始化 MySQL 连接池
        MYSQL_POOL = mysql.connector.pooling.MySQLConnectionPool(
            pool_name="mysql_pool",
            pool_size=10,
            host=MYSQL_CONFIG['host'],
            port=MYSQL_CONFIG['port'],
            database=MYSQL_CONFIG['database'],
            user=MYSQL_CONFIG['user'],
            password=MYSQL_CONFIG['password']
        )
        logger.info("MySQL 连接池初始化成功")
    except Exception as e:
        logger.error(f"MySQL 连接池初始化失败: {str(e)}")
        logger.error(traceback.format_exc())
        MYSQL_POOL = None

# 确保在导入时初始化连接池
init_db_pools()

class pg_connection:
    """PostgreSQL 连接上下文管理器"""
    def __init__(self, max_retries=3):
        self.max_retries = max_retries
        self.retry_count = 0
        self.conn = None
        self.cursor = None
        
    def __enter__(self):
        while self.retry_count < self.max_retries:
            try:
                if PG_POOL is None:
                    init_db_pools()
                    if PG_POOL is None:
                        raise Exception("无法初始化PostgreSQL连接池")
                
                self.conn = PG_POOL.getconn()
                self.cursor = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                return self.cursor
                    
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                self.retry_count += 1
                logger.warning(f"PostgreSQL连接失败，正在重试 ({self.retry_count}/{self.max_retries}): {str(e)}")
                
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
                                if PG_POOL is not None:
                                    PG_POOL.putconn(self.conn)
                            except Exception:
                                pass
                            self.conn = None
                            
                        # 尝试重新初始化连接池
                        init_db_pools()
                        time.sleep(1)  # 短暂暂停，避免立即重试
                    except Exception as init_error:
                        logger.error(f"重新初始化连接池失败: {str(init_error)}")
                else:
                    logger.error("PostgreSQL连接重试失败，已达到最大重试次数")
                    raise
            except Exception as e:
                logger.error(f"获取 PostgreSQL 连接失败: {str(e)}")
                logger.error(traceback.format_exc())
                raise
        
        # 如果所有重试都失败，抛出异常
        if self.retry_count >= self.max_retries:
            raise Exception(f"PostgreSQL连接失败，已达到最大重试次数 ({self.max_retries})")
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if not hasattr(self, 'conn') or self.conn is None:
            return
            
        try:
            if exc_type is not None:
                logger.error(f"PostgreSQL 操作出错: {str(exc_val)}")
                logger.error(traceback.format_exc())
                try:
                    self.conn.rollback()
                except Exception as e:
                    logger.error(f"回滚事务失败: {str(e)}")
            else:
                try:
                    self.conn.commit()
                except Exception as e:
                    logger.error(f"提交事务失败: {str(e)}")
        except Exception as e:
            logger.error(f"处理事务时出错: {str(e)}")
        
        try:
            if hasattr(self, 'cursor') and self.cursor is not None:
                self.cursor.close()
                self.cursor = None
        except Exception as e:
            logger.error(f"关闭游标时出错: {str(e)}")
        
        try:
            if PG_POOL is not None and self.conn is not None:
                PG_POOL.putconn(self.conn)
                self.conn = None
        except Exception as e:
            logger.error(f"归还连接到连接池时出错: {str(e)}")
            try:
                # 如果无法归还连接，尝试关闭它
                if self.conn is not None:
                    self.conn.close()
                    self.conn = None
            except Exception:
                pass

class mysql_connection:
    """用于管理MySQL数据库连接的上下文管理器"""
    
    def __init__(self):
        self.max_retries = 3
        self.retry_count = 0
        self.conn = None
        self.cursor = None
    
    def __enter__(self):
        self.retry_count = 0
        while self.retry_count < self.max_retries:
            try:
                # 尝试从连接池获取连接
                self.conn = MYSQL_POOL.get_connection()
                self.cursor = self.conn.cursor(dictionary=True)
                return self.cursor
            except pooling.PoolError as e:
                self.retry_count += 1
                logger.warning(f"MySQL连接池错误，尝试重新连接 (尝试 {self.retry_count}/{self.max_retries}): {str(e)}")
                
                # 如果超过最大重试次数，抛出异常
                if self.retry_count >= self.max_retries:
                    logger.error(f"无法从连接池获取MySQL连接，已达到最大重试次数: {str(e)}")
                    raise
                
                # 否则，尝试重新初始化连接池并重试
                try:
                    init_db_pools()
                    time.sleep(1)  # 短暂暂停，避免立即重试
                except Exception as init_error:
                    logger.error(f"重新初始化MySQL连接池失败: {str(init_error)}")
            except Exception as e:
                logger.error(f"建立MySQL连接时发生错误: {str(e)}")
                logger.error(traceback.format_exc())
                raise
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            # 如果没有异常，提交事务
            if exc_type is None:
                try:
                    self.conn.commit()
                except Exception as e:
                    logger.error(f"提交MySQL事务时发生错误: {str(e)}")
                    self.conn.rollback()
            else:
                # 如果有异常，回滚事务
                try:
                    self.conn.rollback()
                    logger.warning(f"由于异常，MySQL事务已回滚: {str(exc_val)}")
                except Exception as e:
                    logger.error(f"回滚MySQL事务时发生错误: {str(e)}")
        except Exception as e:
            logger.error(f"处理MySQL事务时发生错误: {str(e)}")
        
        finally:
            # 关闭游标和连接
            if self.cursor:
                try:
                    self.cursor.close()
                except Exception as e:
                    logger.error(f"关闭MySQL游标时发生错误: {str(e)}")
            
            if self.conn:
                try:
                    self.conn.close()
                except Exception as e:
                    logger.error(f"关闭MySQL连接时发生错误: {str(e)}")
        
        # 返回False表示异常不被此方法处理
        return False

# 工作流状态管理功能
def update_workflow_status(workflow_id, status, details=None, error=None):
    """更新工作流状态"""
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # 将详情转换为 JSON 对象，PostgreSQL支持JSONB类型
            if details and isinstance(details, str):
                try:
                    details_json = json.loads(details)
                except json.JSONDecodeError:
                    details_json = {"message": details}
            elif details:
                details_json = details
            else:
                details_json = {}
            
            current_time = datetime.now()
            
            with pg_connection() as cursor:
                # 检查记录是否存在
                cursor.execute(
                    "SELECT workflow_id FROM step0_workflows WHERE workflow_id = %s", 
                    (workflow_id,)
                )
                exists = cursor.fetchone()
                
                if exists:
                    # 更新现有记录
                    cursor.execute(
                        """UPDATE step0_workflows 
                        SET current_status = %s, details = %s, updated_at = %s 
                        WHERE workflow_id = %s""",
                        (status, psycopg2.extras.Json(details_json), current_time, workflow_id)
                    )
                else:
                    # 插入新记录
                    cursor.execute(
                        """INSERT INTO step0_workflows 
                        (workflow_id, current_status, details, created_at, updated_at) 
                        VALUES (%s, %s, %s, %s, %s)""",
                        (workflow_id, status, psycopg2.extras.Json(details_json), current_time, current_time)
                    )
                
                # 添加历史记录
                cursor.execute(
                    """INSERT INTO step0_workflow_history 
                    (workflow_id, status, timestamp, details, error) 
                    VALUES (%s, %s, %s, %s, %s)""",
                    (workflow_id, status, current_time, psycopg2.extras.Json(details_json), error)
                )
            
            logger.debug(f"工作流状态已更新: workflow_id={workflow_id}, status={status}")
            return True
            
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            retry_count += 1
            logger.warning(f"数据库连接错误，尝试重新连接 (尝试 {retry_count}/{max_retries}): {str(e)}")
            
            # 重新初始化连接池
            if retry_count < max_retries:
                try:
                    # 尝试重新初始化连接池
                    init_db_pools()
                    time.sleep(1)  # 短暂暂停，避免立即重试
                except Exception as init_error:
                    logger.error(f"重新初始化连接池失败: {str(init_error)}")
        except Exception as e:
            logger.error(f"更新工作流状态失败: workflow_id={workflow_id}, error={str(e)}")
            logger.error(traceback.format_exc())
            
            # 对于非连接错误，不进行重试
            break
    
    # 所有重试都失败
    if retry_count >= max_retries:
        logger.error(f"更新工作流状态失败，已达到最大重试次数: workflow_id={workflow_id}")
    
    return False

def get_workflow_status(workflow_id):
    """获取工作流状态"""
    try:
        with pg_connection() as cursor:
            # 获取当前工作流状态
            cursor.execute(
                """SELECT workflow_id, current_status as status, details, updated_at, created_at
                FROM step0_workflows 
                WHERE workflow_id = %s""", 
                (workflow_id,)
            )
            workflow = cursor.fetchone()
            
            if not workflow:
                return None
                
            # 获取历史记录
            cursor.execute(
                """SELECT status, timestamp, details, error
                FROM step0_workflow_history
                WHERE workflow_id = %s
                ORDER BY timestamp DESC""",
                (workflow_id,)
            )
            history_rows = cursor.fetchall()
            
            # 将历史记录转换为列表
            history = []
            for row in history_rows:
                history_item = {
                    'status': row['status'],
                    'timestamp': row['timestamp'],
                    'details': row['details'],
                    'error': row['error']
                }
                history.append(history_item)
            
            # 将历史记录添加到结果中
            result = dict(workflow)
            result['history'] = history
            
            return result
    except Exception as e:
        logger.error(f"获取工作流状态失败: workflow_id={workflow_id}, error={str(e)}")
        logger.error(traceback.format_exc())
        return None

def get_all_workflow_status(status_filter=None):
    """获取所有工作流状态"""
    try:
        with pg_connection() as cursor:
            # 根据是否有状态过滤器构建查询
            if status_filter:
                cursor.execute(
                    """SELECT workflow_id, current_status as status, details, updated_at, created_at
                    FROM step0_workflows 
                    WHERE current_status = %s
                    ORDER BY updated_at DESC""", 
                    (status_filter,)
                )
            else:
                cursor.execute(
                    """SELECT workflow_id, current_status as status, details, updated_at, created_at
                    FROM step0_workflows 
                    ORDER BY updated_at DESC"""
                )
            
            workflows = cursor.fetchall()
            
            # 为空结果返回空列表
            if not workflows:
                return []
            
            # 创建结果字典，用workflow_id作为键
            results = {}
            for workflow in workflows:
                wf_id = workflow['workflow_id']
                results[wf_id] = dict(workflow)
                results[wf_id]['history'] = []
            
            # 获取所有相关的历史记录
            workflow_ids = [w['workflow_id'] for w in workflows]
            
            # PostgreSQL允许使用IN语句
            placeholders = ','.join(['%s'] * len(workflow_ids))
            cursor.execute(
                f"""SELECT workflow_id, status, timestamp, details, error
                FROM step0_workflow_history
                WHERE workflow_id IN ({placeholders})
                ORDER BY timestamp DESC""",
                workflow_ids
            )
            
            history_rows = cursor.fetchall()
            
            # 将历史记录添加到相应的工作流中
            for row in history_rows:
                wf_id = row['workflow_id']
                if wf_id in results:
                    history_item = {
                        'status': row['status'],
                        'timestamp': row['timestamp'],
                        'details': row['details'],
                        'error': row['error']
                    }
                    results[wf_id]['history'].append(history_item)
            
            return results
    except Exception as e:
        logger.error(f"获取所有工作流状态失败: error={str(e)}")
        logger.error(traceback.format_exc())
        return {}

# 链接缓存管理功能
def get_link_cache(homepage_url):
    """从数据库获取特定主页的历史链接缓存"""
    try:
        with pg_connection() as cursor:
            cursor.execute(
                """SELECT link FROM step1_link_cache 
                WHERE homepage_url = %s""",
                (homepage_url,)
            )
            
            # 提取链接列表
            links = [row[0] for row in cursor.fetchall()]
            
            logger.debug(f"从数据库加载了 {len(links)} 个历史链接，homepage_url: {homepage_url}")
            return links
    except Exception as e:
        logger.error(f"获取链接缓存失败: homepage_url={homepage_url}, error={str(e)}")
        logger.error(traceback.format_exc())
        return []

def save_link_cache(homepage_url, links):
    """保存历史链接缓存到数据库"""
    if not links:
        logger.warning(f"尝试保存空链接列表，homepage_url: {homepage_url}")
        return True
    
    try:
        with pg_connection() as cursor:
            # 批量插入新记录，使用ON CONFLICT DO NOTHING保留已存在的链接
            current_time = datetime.now()
            insert_data = [(homepage_url, link, current_time) for link in links]
            
            # 使用executemany批量插入
            for homepage, link, time in insert_data:
                cursor.execute(
                    """INSERT INTO step1_link_cache 
                    (homepage_url, link, created_at) 
                    VALUES (%s, %s, %s)
                    ON CONFLICT (homepage_url, link) DO NOTHING""",
                    (homepage, link, time)
                )
            
            logger.debug(f"历史链接缓存已保存到数据库，homepage_url: {homepage_url}, 链接数量: {len(links)}")
            return True
    except Exception as e:
        logger.error(f"保存链接缓存失败: homepage_url={homepage_url}, error={str(e)}")
        logger.error(traceback.format_exc())
        return False

def save_new_links(homepage_url, data):
    """保存新发现的链接到数据库"""
    try:
        new_links = data.get('new_links', [])
        if not new_links:
            logger.warning(f"没有新链接需要保存，homepage_url: {homepage_url}")
            return True
        
        batch_id = data.get('batch_id', f"batch_{datetime.now().strftime('%Y%m%d%H%M%S')}")
        source = data.get('source', '')
        note = data.get('note', '')
        current_time = datetime.now()
        
        with pg_connection() as cursor:
            # 批量插入新链接
            insert_data = [
                (current_time, homepage_url, link, source, note, batch_id, current_time) 
                for link in new_links
            ]
            
            # 使用executemany批量插入
            cursor.executemany(
                """INSERT INTO step1_new_links 
                (timestamp, homepage_url, link, source, note, batch_id, created_at) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                insert_data
            )
            
            logger.info(f"已保存 {len(new_links)} 个新链接到数据库，homepage_url: {homepage_url}, 批次ID: {batch_id}")
            return True
    except Exception as e:
        logger.error(f"保存新链接失败: homepage_url={homepage_url}, error={str(e)}")
        logger.error(traceback.format_exc())
        return False

def get_latest_links(max_links=50):
    """获取最新发现的链接，限制数量"""
    try:
        with pg_connection() as cursor:
            # 先获取最新的批次ID
            cursor.execute(
                """SELECT DISTINCT batch_id, MAX(created_at) as batch_time
                FROM step1_new_links 
                GROUP BY batch_id 
                ORDER BY batch_time DESC 
                LIMIT 1"""
            )
            
            latest_batch = cursor.fetchone()
            
            if not latest_batch:
                logger.warning("没有找到任何批次")
                return []
                
            latest_batch_id = latest_batch['batch_id']
            
            # 从最新批次中获取链接
            cursor.execute(
                """SELECT id, link, homepage_url, source, note, batch_id, created_at 
                FROM step1_new_links 
                WHERE batch_id = %s
                ORDER BY created_at DESC 
                LIMIT %s""",
                (latest_batch_id, max_links)
            )
            
            # 转换为字典列表
            columns = [desc[0] for desc in cursor.description]
            links = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            logger.debug(f"从数据库最新批次 {latest_batch_id} 获取了 {len(links)} 个链接")
            return links
    except Exception as e:
        logger.error(f"获取最新链接失败: error={str(e)}")
        logger.error(traceback.format_exc())
        return []

def get_newly_discovered_links(max_batches=10):
    """获取最近发现的链接，按批次分组"""
    try:
        with pg_connection() as cursor:
            # 首先获取最新的几个批次
            cursor.execute(
                """SELECT DISTINCT batch_id, MIN(created_at) as batch_time
                FROM step1_new_links 
                GROUP BY batch_id 
                ORDER BY batch_time DESC 
                LIMIT %s""",
                (max_batches,)
            )
            
            batches = cursor.fetchall()
            
            if not batches:
                return {}
                
            # 为每个批次获取链接
            result = {}
            batch_ids = [batch['batch_id'] for batch in batches]
            
            # 使用PostgreSQL的IN语句
            placeholders = ','.join(['%s'] * len(batch_ids))
            cursor.execute(
                f"""SELECT id, link, homepage_url, source, note, batch_id, created_at
                FROM step1_new_links 
                WHERE batch_id IN ({placeholders})
                ORDER BY created_at DESC""",
                batch_ids
            )
            
            rows = cursor.fetchall()
            
            # 将链接按照批次分组
            for row in rows:
                batch_id = row['batch_id']
                if batch_id not in result:
                    result[batch_id] = {
                        'links': [],
                        'homepage_url': row['homepage_url'],
                        'created_at': row['created_at']
                    }
                
                result[batch_id]['links'].append({
                    'id': row['id'],
                    'link': row['link'],
                    'source': row['source'],
                    'note': row['note']
                })
            
            logger.debug(f"从数据库获取了 {len(result)} 个批次的新链接")
            return result
    except Exception as e:
        logger.error(f"获取新发现的链接失败: error={str(e)}")
        logger.error(traceback.format_exc())
        return {}

def get_valid_links(max_links=20, latest_workflow_id=None):
    """从数据库获取有效链接
    
    参数:
    max_links - 最大获取数量
    latest_workflow_id - 如果提供，则仅获取该工作流ID的有效链接
    """
    try:
        with pg_connection() as cursor:
            # 如果未提供workflow_id，先获取最新的分析工作流ID
            if not latest_workflow_id:
                try:
                    cursor.execute(
                        """SELECT workflow_id, MAX(updated_at) as workflow_time
                        FROM step2_link_analysis 
                        GROUP BY workflow_id 
                        ORDER BY workflow_time DESC 
                        LIMIT 1"""
                    )
                    
                    latest_workflow = cursor.fetchone()
                    
                    if latest_workflow:
                        latest_workflow_id = latest_workflow['workflow_id']
                        logger.info(f"找到最新的工作流ID: {latest_workflow_id}")
                    else:
                        logger.warning("没有找到任何工作流，将获取所有有效链接")
                except Exception as e:
                    logger.error(f"获取最新工作流ID时出错: {str(e)}")
                    logger.error(traceback.format_exc())
                    # 出错时，继续获取所有有效链接
            
            # 构建SQL查询
            if latest_workflow_id:
                sql = """SELECT link_id, link, confidence, reason, workflow_id, created_at 
                      FROM step2_link_analysis 
                      WHERE is_valid = TRUE AND workflow_id = %s
                      ORDER BY created_at DESC 
                      LIMIT %s"""
                params = (latest_workflow_id, max_links)
                logger.info(f"根据工作流ID获取有效链接: workflow_id={latest_workflow_id}")
            else:
                sql = """SELECT link_id, link, confidence, reason, workflow_id, created_at 
                      FROM step2_link_analysis 
                      WHERE is_valid = TRUE 
                      ORDER BY created_at DESC 
                      LIMIT %s"""
                params = (max_links,)
                logger.info(f"获取所有有效链接，最大数量: {max_links}")
            
            try:
                # 执行查询
                cursor.execute(sql, params)
                
                # 转换为字典列表
                columns = [desc[0] for desc in cursor.description]
                links = [dict(zip(columns, row)) for row in cursor.fetchall()]
                
                logger.info(f"从数据库获取了 {len(links)} 个有效链接" + 
                           (f" (工作流ID: {latest_workflow_id})" if latest_workflow_id else ""))
                return links
            except Exception as e:
                logger.error(f"执行链接查询时出错: {str(e)}")
                logger.error(traceback.format_exc())
                return []
    except Exception as e:
        logger.error(f"获取有效链接失败: error={str(e)}")
        logger.error(traceback.format_exc())
        return []

# 链接分析结果管理功能
def save_link_analysis(link_id, link, is_valid, analysis_result, workflow_id, confidence=0, reason=''):
    """保存链接分析结果到step2_link_analysis表"""
    try:
        current_time = datetime.now()
            
        with pg_connection() as cursor:
            # 将analysis_result转换为JSON对象，如果不是JSON对象
            if analysis_result and not isinstance(analysis_result, dict):
                try:
                    if isinstance(analysis_result, str):
                        analysis_result = json.loads(analysis_result)
                    else:
                        analysis_result = {"data": str(analysis_result)}
                except json.JSONDecodeError:
                    analysis_result = {"raw_text": analysis_result}
            
            # 插入或更新分析结果
            cursor.execute(
                """INSERT INTO step2_link_analysis 
                (link_id, link, is_valid, analysis_result, confidence, reason, workflow_id, created_at, updated_at) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (link_id) DO UPDATE 
                SET is_valid = %s, 
                    analysis_result = %s, 
                    confidence = %s, 
                    reason = %s, 
                    workflow_id = %s, 
                    updated_at = %s""",
                (
                    link_id, link, is_valid, psycopg2.extras.Json(analysis_result), confidence, reason, 
                    workflow_id, current_time, current_time,
                    is_valid, psycopg2.extras.Json(analysis_result), confidence, reason, workflow_id, current_time
                )
            )
            
            logger.debug(f"链接分析结果已保存: link_id={link_id}, is_valid={is_valid}")
            return True
    except Exception as e:
        logger.error(f"保存链接分析结果失败: link_id={link_id}, error={str(e)}")
        logger.error(traceback.format_exc())
        return False

def save_analysis_batch(workflow_id, batch_id, analysis_data):
    """保存批量分析结果到step2_analysis_results表"""
    try:
        current_time = datetime.now()
        
        with pg_connection() as cursor:
            # 插入批量分析结果
            cursor.execute(
                """INSERT INTO step2_analysis_results 
                (workflow_id, batch_id, analysis_data, created_at) 
                VALUES (%s, %s, %s, %s)""",
                (workflow_id, batch_id, psycopg2.extras.Json(analysis_data), current_time)
            )
            
            logger.debug(f"批量分析结果已保存: workflow_id={workflow_id}, batch_id={batch_id}")
            return True
    except Exception as e:
        logger.error(f"保存批量分析结果失败: workflow_id={workflow_id}, batch_id={batch_id}, error={str(e)}")
        logger.error(traceback.format_exc())
        return False

def get_link_analysis(link_id):
    """获取链接分析结果"""
    try:
        with pg_connection() as cursor:
            cursor.execute(
                """SELECT link_id, link, is_valid, analysis_result, confidence, reason, 
                workflow_id, created_at, updated_at
                FROM step2_link_analysis 
                WHERE link_id = %s""",
                (link_id,)
            )
            
            row = cursor.fetchone()
            
            if row:
                # 将行转换为字典
                result = {
                    'link_id': row['link_id'],
                    'link': row['link'],
                    'is_valid': row['is_valid'],
                    'analysis_result': row['analysis_result'],
                    'confidence': row['confidence'],
                    'reason': row['reason'],
                    'workflow_id': row['workflow_id'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                }
                return result
            
            return None
    except Exception as e:
        logger.error(f"获取链接分析结果失败: link_id={link_id}, error={str(e)}")
        logger.error(traceback.format_exc())
        return None

# 内容管理功能
def save_content(workflow_id, content_type, content, metadata=None):
    """保存内容到news_content.step3_content表"""
    try:
        # 提取和转换必要数据
        link_id = None
        title = ""
        article_content = ""
        event_tags = "[]"
        space_tags = "[]"
        cat_tags = "[]"
        impact_factors = "[]"  # 添加impact_factors字段默认值
        publish_time = None
        importance = "低"
        state = "[]"
        source_note = ""
        homepage_url = ""
        
        # 从metadata中提取链接ID和其他元数据
        metadata_obj = None
        if metadata:
            try:
                if isinstance(metadata, str):
                    metadata_obj = json.loads(metadata)
                else:
                    metadata_obj = metadata
                    
                link_id = metadata_obj.get('link_id')
                source_note = metadata_obj.get('source_note', '')
                homepage_url = metadata_obj.get('homepage_url', '')
            except Exception as e:
                logger.error(f"解析元数据时出错: {str(e)}")
        
        # 如果元数据中没有link_id，使用workflow_id
        if not link_id:
            link_id = workflow_id
            
        # 从content中提取字段
        content_obj = None
        if content:
            try:
                if isinstance(content, str):
                    content_obj = json.loads(content)
                    logger.info(f"content是字符串，解析后: {content_obj.keys()}")
                else:
                    content_obj = content
                    logger.info(f"content是对象，键: {content_obj.keys()}")
                    
                title = content_obj.get('title', '')
                logger.info(f"db_utils.save_content: 提取的标题 [{title}]，类型: {type(title)}，长度: {len(title)}")
                if title:
                    # 记录标题的前20个字符的十六进制表示
                    hex_chars = ' '.join(hex(ord(c)) for c in title[:20])
                    logger.info(f"标题前20个字符的十六进制: {hex_chars}")
                
                article_content = content_obj.get('content', '')
                
                # 转换标签为JSON字符串
                if 'event_tags' in content_obj:
                    event_tags = json.dumps(content_obj['event_tags'])
                if 'space_tags' in content_obj:
                    space_tags = json.dumps(content_obj['space_tags'])
                if 'cat_tags' in content_obj:
                    cat_tags = json.dumps(content_obj['cat_tags'])
                if 'impact_factors' in content_obj:  # 添加对impact_factors的处理
                    impact_factors = json.dumps(content_obj['impact_factors'])
                    
                # 处理publish_time - 修复空字符串问题
                publish_time = content_obj.get('publish_time')
                if publish_time == '':
                    publish_time = None
                elif publish_time and len(publish_time) > 10:
                    # 如果日期格式过长，只保留年月日部分
                    publish_time = publish_time[:10]
                
                importance = content_obj.get('importance', '低')
                
                if 'state' in content_obj:
                    state = json.dumps(content_obj['state'])
            except Exception as e:
                logger.error(f"解析内容时出错: {str(e)}")
                logger.error(traceback.format_exc())
                # 如果无法解析，则将原内容存储为文本
                article_content = str(content)
            
        with mysql_connection() as cursor:
            try:
                # 记录即将插入数据库的标题
                logger.info(f"即将插入数据库的标题: [{title}]")
                
                # 记录变量类型和长度，帮助诊断字符编码问题
                logger.info(f"插入前标题长度: {len(title)}, 内容长度: {len(article_content)}")
                
                # 直接插入到news_content.step3_content表
                cursor.execute(
                        """INSERT INTO news_content.step3_content 
                        (link_id, title, content, event_tags, space_tags, cat_tags, impact_factors,
                        publish_time, importance, state, source_note, homepage_url, workflow_id) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        title = %s,
                        content = %s,
                        event_tags = %s,
                        space_tags = %s,
                        cat_tags = %s,
                        impact_factors = %s,
                        publish_time = %s,
                        importance = %s,
                        state = %s,
                        source_note = %s,
                        homepage_url = %s,
                        workflow_id = %s""",
                        (
                            link_id, title, article_content, event_tags, space_tags, cat_tags, impact_factors,
                            publish_time, importance, state, source_note, homepage_url, workflow_id,
                            title, article_content, event_tags, space_tags, cat_tags, impact_factors,
                            publish_time, importance, state, source_note, homepage_url, workflow_id
                        )
                )
                
                # 插入后验证
                last_id = cursor.lastrowid
                if last_id:
                    try:
                        cursor.execute(
                            "SELECT title FROM news_content.step3_content WHERE id = %s", 
                            (last_id,)
                        )
                        result = cursor.fetchone()
                        if result:
                            logger.info(f"插入后从数据库读取的标题: [{result['title']}], 长度: {len(result['title'] or '')}")
                    except Exception as check_err:
                        logger.error(f"验证插入失败: {str(check_err)}")
                
                return last_id
            except Exception as e:
                logger.error(f"插入数据到news_content.step3_content表失败: {str(e)}")
                logger.error(traceback.format_exc())
                return None
    except Exception as e:
        logger.error(f"保存内容失败: workflow_id={workflow_id}, error={str(e)}")
        logger.error(traceback.format_exc())
        return None

def get_content(content_id=None, workflow_id=None, content_type=None):
    """从news_content.step3_content表获取内容"""
    try:
        with mysql_connection() as cursor:
            if content_id:
                cursor.execute(
                    """SELECT id, link_id, title, content, event_tags, space_tags, cat_tags, impact_factors,
                    publish_time, importance, state, source_note, homepage_url, workflow_id, created_at
                    FROM news_content.step3_content 
                    WHERE id = %s""",
                    (content_id,)
                )
            elif workflow_id:
                cursor.execute(
                    """SELECT id, link_id, title, content, event_tags, space_tags, cat_tags, impact_factors,
                    publish_time, importance, state, source_note, homepage_url, workflow_id, created_at 
                    FROM news_content.step3_content 
                    WHERE workflow_id = %s
                    ORDER BY created_at DESC 
                    LIMIT 50""",
                    (workflow_id,)
                )
            else:
                logger.warning("获取内容需要指定 content_id 或 workflow_id")
                return None
            
            results = cursor.fetchall()
            
            if not results:
                return None
                
            # 如果只查询一个内容，返回单个结果
            if content_id:
                result = results[0]
                # 解析 JSON 格式的字段
                try:
                    if result['event_tags']:
                        result['event_tags'] = json.loads(result['event_tags'])
                except json.JSONDecodeError:
                    result['event_tags'] = []
                    
                try:
                    if result['space_tags']:
                        result['space_tags'] = json.loads(result['space_tags'])
                except json.JSONDecodeError:
                    result['space_tags'] = []
                    
                try:
                    if result['cat_tags']:
                        result['cat_tags'] = json.loads(result['cat_tags'])
                except json.JSONDecodeError:
                    result['cat_tags'] = []
                    
                try:
                    if result['impact_factors']:  # 添加对impact_factors的解析
                        result['impact_factors'] = json.loads(result['impact_factors'])
                except json.JSONDecodeError:
                    result['impact_factors'] = []
                    
                try:
                    if result['state']:
                        result['state'] = json.loads(result['state'])
                except json.JSONDecodeError:
                    result['state'] = []
                
                return result
            else:
                # 返回多个结果
                processed_results = []
                for result in results:
                    # 解析 JSON 格式的字段
                    try:
                        if result['event_tags']:
                            result['event_tags'] = json.loads(result['event_tags'])
                    except json.JSONDecodeError:
                        result['event_tags'] = []
                        
                    try:
                        if result['space_tags']:
                            result['space_tags'] = json.loads(result['space_tags'])
                    except json.JSONDecodeError:
                        result['space_tags'] = []
                        
                    try:
                        if result['cat_tags']:
                            result['cat_tags'] = json.loads(result['cat_tags'])
                    except json.JSONDecodeError:
                        result['cat_tags'] = []
                
                    try:
                        if result['impact_factors']:  # 添加对impact_factors的解析
                            result['impact_factors'] = json.loads(result['impact_factors'])
                    except json.JSONDecodeError:
                        result['impact_factors'] = []
                    
                    try:
                        if result['state']:
                            result['state'] = json.loads(result['state'])
                    except json.JSONDecodeError:
                        result['state'] = []
                    
                    processed_results.append(result)
                
                return processed_results
            
    except Exception as e:
        logger.error(f"获取内容失败: {str(e)}")
        logger.error(traceback.format_exc())
        return None

# 主页URL管理功能
def get_homepage_urls(limit=100, active_only=True):
    """获取主页URL列表"""
    try:
        with mysql_connection() as cursor:
            if active_only:
                cursor.execute(
                    """SELECT id, link, source, note, active, created_at, updated_at 
                    FROM homepage_urls 
                    WHERE active = TRUE 
                    ORDER BY created_at 
                    LIMIT %s""",
                    (limit,)
                )
            else:
                cursor.execute(
                    """SELECT id, link, source, note, active, created_at, updated_at 
                    FROM homepage_urls 
                    ORDER BY created_at 
                    LIMIT %s""",
                    (limit,)
                )
            
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"获取主页URL列表失败: error={str(e)}")
        logger.error(traceback.format_exc())
        return []

def add_homepage_url(link, source=None, note=None, active=True):
    """添加主页URL"""
    try:
        with mysql_connection() as cursor:
            cursor.execute(
                """INSERT INTO homepage_urls 
                (link, source, note, active, created_at, updated_at) 
                VALUES (%s, %s, %s, %s, NOW(), NOW())""",
                (link, source, note, active)
            )
            
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"添加主页URL失败: link={link}, error={str(e)}")
        logger.error(traceback.format_exc())
        return None

def update_homepage_url(url_id, active=True, note=None):
    """更新主页URL状态"""
    try:
        with mysql_connection() as cursor:
            if note is not None:
                cursor.execute(
                    """UPDATE homepage_urls 
                    SET active = %s, note = %s, updated_at = NOW() 
                    WHERE id = %s""",
                    (active, note, url_id)
                )
            else:
                cursor.execute(
                    """UPDATE homepage_urls 
                    SET active = %s, updated_at = NOW() 
                    WHERE id = %s""",
                    (active, url_id)
                )
            
            return True
    except Exception as e:
        logger.error(f"更新主页URL状态失败: url_id={url_id}, error={str(e)}")
        logger.error(traceback.format_exc())
        return False

# 健康检查函数
def check_db_connections():
    """检查数据库连接状态"""
    pg_ok = False
    mysql_ok = False
    
    # 检查 PostgreSQL 连接
    try:
        with pg_connection() as cursor:
            cursor.execute("SELECT 1")
            pg_ok = cursor.fetchone()[0] == 1
    except Exception as e:
        logger.error(f"PostgreSQL 连接检查失败: {str(e)}")
    
    # 检查 MySQL 连接
    try:
        with mysql_connection() as cursor:
            cursor.execute("SELECT 1")
            mysql_ok = cursor.fetchone()['1'] == 1
    except Exception as e:
        logger.error(f"MySQL 连接检查失败: {str(e)}")
    
    return {
        "postgres": pg_ok,
        "mysql": mysql_ok,
        "all_ok": pg_ok and mysql_ok
    } 