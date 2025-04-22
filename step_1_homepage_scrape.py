from firecrawl.firecrawl import FirecrawlApp
import config
import json
from datetime import datetime
import time
import os
import logging
import traceback
import mysql.connector
import db_utils

# 配置日志系统
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
log_file = os.path.join(log_dir, f"homepage_scrape_{datetime.now().strftime('%Y%m%d')}.log")

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()  # 同时输出到控制台
    ]
)
logger = logging.getLogger("HomepageScrape")

# 确保环境变量正确设置
if not config.check_env_vars():
    logger.error("环境变量配置错误，请检查.env文件")
    exit(1)

class HomepageScraper:
    def __init__(self):
        """初始化抓取器"""
        # 使用config.py中定义的API_KEY
        self.app = FirecrawlApp(api_key=config.API_KEY)
        logger.info(f"初始化 FirecrawlApp API密钥: {config.API_KEY[:5]}...{config.API_KEY[-5:]}")

    def _load_link_history(self, homepage_url):
        """从数据库加载历史链接缓存"""
        try:
            links = db_utils.get_link_cache(homepage_url)
            logger.debug(f"从数据库加载了 {len(links)} 个历史链接")
            return links
        except Exception as e:
            logger.error(f"加载历史链接缓存时出错: {e}")
            return []

    def _save_link_history(self, homepage_url, links):
        """保存历史链接缓存到数据库"""
        try:
            success = db_utils.save_link_cache(homepage_url, links)
            if success:
                logger.debug(f"历史链接缓存已保存到数据库，homepage_url: {homepage_url}, 链接数量: {len(links)}")
            else:
                logger.error(f"保存历史链接缓存到数据库失败，homepage_url: {homepage_url}")
            return success
        except Exception as e:
            logger.error(f"保存历史链接缓存时出错: {e}")
            return False

    def _save_new_links(self, new_links_data):
        """保存新发现的链接到数据库"""
        try:
            # 生成batch_id
            batch_id = f"batch_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # 记录总链接数
            total_links = 0
            
            # 为每个homepage_url保存新链接
            for homepage_url in new_links_data:
                # 为数据添加batch_id
                new_links_data[homepage_url]['batch_id'] = batch_id
                # 保存到数据库
                db_utils.save_new_links(homepage_url, new_links_data[homepage_url])
                total_links += len(new_links_data[homepage_url].get('new_links', []))
                
            logger.info(f"已保存 {total_links} 个新链接到数据库，批次ID: {batch_id}")
            return batch_id
            
        except Exception as e:
            logger.error(f"保存新链接时出错: {str(e)}\n{traceback.format_exc()}")
            return None

    def read_homepage_urls(self):
        """从数据库读取主页URL"""
        try:
            # 连接到MySQL数据库
            conn = mysql.connector.connect(**config.MYSQL_CONFIG)
            cursor = conn.cursor(dictionary=True)
            
            # 查询所有活跃的homepage_urls
            cursor.execute("SELECT * FROM homepage_urls WHERE active = TRUE")
            rows = cursor.fetchall()
            
            # 关闭连接
            cursor.close()
            conn.close()
            
            # 构建URL字典
            urls_info = {}
            for row in rows:
                url = row['link']
                info = {
                    'note': row['note'] or '',
                    'source': row['source'] or ''
                }
                urls_info[url] = info
            
            logger.info(f"从数据库读取了 {len(urls_info)} 个活跃主页URL")
            return urls_info
        except Exception as e:
            logger.error(f"从数据库读取homepage_urls时出错: {str(e)}\n{traceback.format_exc()}")
            return {}

    def extract_links_from_page(self, url):
        """使用scrape_url方法从页面提取链接"""
        max_retries = config.MAX_RETRIES
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                if retry_count > 0:
                    # 固定15秒等待时间
                    wait_time = 15
                    logger.info(f"第 {retry_count} 次重试，等待 {wait_time} 秒...")
                    time.sleep(wait_time)
                
                logger.info(f"正在使用scrape_url方法获取 {url} 的链接...")
                
                # 使用scrape_url功能获取页面内容和链接
                result = self.app.scrape_url(url, params={
                    'formats': ['links'],  # 获取链接
                    'timeout': 60000  # 超时时间（毫秒）
                })
                
                if result and 'links' in result:
                    # 移除自引用链接
                    links = [link for link in result['links'] if link != url]
                    
                    # 过滤掉一些不需要的路径
                    excluded_patterns = [
                        '/tag/', '/category/', '/author/',
                        '/search/', '/page/', '/wp-content/',
                        '/wp-admin/', '/wp-includes/',
                        '/login', '/register', '/account',
                        '.jpg', '.jpeg', '.png', '.gif',
                        '.css', '.js', '.xml', '.pdf','start=',
                        'javascript:'
                    ]
                    
                    filtered_links = []
                    for link in links:
                        exclude = False
                        for pattern in excluded_patterns:
                            if pattern in link:
                                exclude = True
                                break
                        if not exclude:
                            filtered_links.append(link)
                    
                    logger.info(f"原始链接数量: {len(result['links'])}, 去除自引用后: {len(links)}, 过滤后: {len(filtered_links)}")
                    return filtered_links
                
                logger.warning("没有找到链接或返回结果为空")
                return []
                
            except Exception as e:
                logger.error(f"从页面提取链接时出错 {url}: {str(e)}")
                if "Rate limit exceeded" in str(e):
                    retry_count += 1
                    if retry_count <= max_retries:
                        # 从错误消息中提取等待时间
                        try:
                            error_str = str(e)
                            wait_info = error_str.split("please retry after ")[1].split("s,")[0]
                            wait_seconds = int(float(wait_info)) 
                            logger.info(f"达到速率限制，等待 {wait_seconds} 秒后重试...")
                            time.sleep(wait_seconds)
                        except:
                            # 固定15秒等待时间
                            wait_time = 15
                            logger.info(f"达到速率限制，等待 {wait_time} 秒后重试...")
                            time.sleep(wait_time)
                    else:
                        logger.warning(f"达到最大重试次数，放弃获取链接")
                        return []
                else:
                    # 对于非速率限制错误，尝试一次重试
                    if "timeout" in str(e).lower() and retry_count < max_retries:
                        retry_count += 1
                        # 固定15秒等待时间
                        wait_time = 15
                        logger.info(f"请求超时，等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                    else:
                        logger.warning(f"无法处理的错误，放弃获取链接")
                        return []
        
        return []

    def check_for_new_links(self):
        """检查新链接"""
        workflow_id = f"homepage_scrape_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        logger.info(f"开始新链接检查，工作流ID: {workflow_id}")
        
        # 更新工作流状态为开始
        db_utils.update_workflow_status(workflow_id, "SCRAPING", details={"message": "开始检查主页新链接"})
        
        urls_info = self.read_homepage_urls()
        if not urls_info:
            logger.warning("没有找到要监控的URL")
            db_utils.update_workflow_status(workflow_id, "COMPLETED", details={"message": "没有找到要监控的URL"})
            return

        new_links_found = {}
        
        # 统计信息
        total_urls = len(urls_info)
        processed_urls = 0
        total_new_links = 0
        
        for homepage_url, info in urls_info.items():
            processed_urls += 1
            logger.info(f"\n正在检查主页 [{processed_urls}/{total_urls}]: {homepage_url}")
            logger.info(f"备注: {info['note']}")
            
            try:
                # 获取当前页面的所有链接
                current_links = self.extract_links_from_page(homepage_url)
                logger.info(f"发现 {len(current_links)} 个链接")
                
                # 获取这个主页的历史链接
                historical_links = self._load_link_history(homepage_url)
                logger.info(f"历史链接数量: {len(historical_links)}")
                
                # 找出新链接
                new_links = [link for link in current_links if link not in historical_links]
                
                if new_links:
                    logger.info(f"发现 {len(new_links)} 个新链接")
                    # 限制显示的链接数量，避免输出过长
                    display_limit = min(10, len(new_links))
                    for i, link in enumerate(new_links[:display_limit]):
                        logger.info(f"  - {link}")
                    
                    if len(new_links) > display_limit:
                        logger.info(f"  ... 还有 {len(new_links) - display_limit} 个新链接未显示")
                    
                    # 更新历史记录
                    updated_links = list(set(historical_links + current_links))
                    self._save_link_history(homepage_url, updated_links)
                    logger.info(f"历史链接更新至 {len(updated_links)} 个")
                    
                    # 记录新链接
                    new_links_found[homepage_url] = {
                        'note': info['note'],
                        'source': info['source'],
                        'new_links': new_links,
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    total_new_links += len(new_links)
                    
                else:
                    logger.info("没有发现新链接")
                
                # 每次检查后暂停一段时间，避免请求过于频繁
                if processed_urls < total_urls:  # 最后一个URL不需要等待
                    wait_time = 15
                    logger.info(f"等待 {wait_time} 秒后继续下一个URL...")
                    time.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"处理主页时出错 {homepage_url}: {str(e)}\n{traceback.format_exc()}")
                continue

        # 如果发现了新链接，保存它们到数据库
        if new_links_found:
            batch_id = self._save_new_links(new_links_found)
            logger.info(f"\n总计发现并保存 {total_new_links} 个新链接，来自 {len(new_links_found)} 个网站")
            db_utils.update_workflow_status(workflow_id, "COMPLETED", 
                                           details={
                                               "new_links_count": total_new_links,
                                               "sites_count": len(new_links_found),
                                               "batch_id": batch_id
                                           })
        else:
            logger.info("\n未发现任何新链接")
            db_utils.update_workflow_status(workflow_id, "COMPLETED", 
                                          details={"message": "未发现任何新链接"})
        
        return new_links_found

def main(interval_minutes=None):
    """主函数，可选择定时运行"""
    scraper = HomepageScraper()
    
    def run_check():
        logger.info(f"\n开始检查 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        scraper.check_for_new_links()
        logger.info(f"检查完成 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if interval_minutes:
        logger.info(f"设置为每 {interval_minutes} 分钟运行一次")
        while True:
            try:
                run_check()
                logger.info(f"等待 {interval_minutes} 分钟后进行下一次检查...")
                time.sleep(interval_minutes * 60)
            except KeyboardInterrupt:
                logger.info("检测到用户中断，程序退出")
                break
            except Exception as e:
                logger.error(f"运行过程中发生错误: {str(e)}\n{traceback.format_exc()}")
                logger.info(f"等待 {interval_minutes} 分钟后重试...")
                time.sleep(interval_minutes * 60)
    else:
        run_check()

if __name__ == "__main__":
    # 设置为None表示只运行一次，或者设置分钟数进行定时运行
    # 例如：main(interval_minutes=60) 表示每小时运行一次
    try:
        main()
    except KeyboardInterrupt:
        logger.info("检测到用户中断，程序退出")
    except Exception as e:
        logger.error(f"程序执行出错: {str(e)}\n{traceback.format_exc()}") 