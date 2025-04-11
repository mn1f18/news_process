from firecrawl.firecrawl import FirecrawlApp
import config
import json
import pandas as pd
from datetime import datetime, timedelta
import time
import os
import random
import logging
import shutil

# 配置日志系统
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
log_file = os.path.join(log_dir, f"homepage_monitor_{datetime.now().strftime('%Y%m%d')}.log")

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()  # 同时输出到控制台
    ]
)
logger = logging.getLogger("HomepageMonitor")

# 确保环境变量正确设置
if not config.check_env_vars():
    logger.error("环境变量配置错误，请检查.env文件")
    exit(1)

class HomepageMonitor:
    def __init__(self, excel_path, cache_file="link_cache.json", new_links_file="new_links.json", archive_dir="archives"):
        """初始化监控器"""
        # 使用config.py中定义的API_KEY
        self.app = FirecrawlApp(api_key=config.API_KEY)
        self.excel_path = excel_path
        self.cache_file = cache_file
        self.new_links_file = new_links_file
        self.archive_dir = archive_dir
        
        # 确保存档目录存在
        if not os.path.exists(self.archive_dir):
            os.makedirs(self.archive_dir)
            
        self.link_history = self._load_link_history()
        logger.info(f"使用 FirecrawlApp API密钥: {config.API_KEY[:5]}...{config.API_KEY[-5:]}")

    def _load_link_history(self):
        """加载历史链接缓存"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"加载历史链接缓存时出错: {e}")
            return {}

    def _save_link_history(self):
        """保存历史链接缓存"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.link_history, f, ensure_ascii=False, indent=2)
            logger.debug("历史链接缓存已保存")
        except Exception as e:
            logger.error(f"保存历史链接缓存时出错: {e}")

    def _save_new_links(self, new_links_data):
        """保存新发现的链接"""
        try:
            # 读取现有的新链接数据（如果存在）
            existing_data = {}
            if os.path.exists(self.new_links_file):
                with open(self.new_links_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)

            # 更新数据
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # 生成batch_id
            batch_id = f"batch_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            if timestamp not in existing_data:
                # 为每个homepage_url的数据添加batch_id
                for homepage_url in new_links_data:
                    new_links_data[homepage_url]['batch_id'] = batch_id
                existing_data[timestamp] = new_links_data

            # 保存更新后的数据
            with open(self.new_links_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"新链接已保存，批次ID: {batch_id}")
            
            # 检查是否需要归档
            self._check_and_archive()
            
        except Exception as e:
            logger.error(f"保存新链接时出错: {e}")

    def _check_and_archive(self, days_threshold=30, size_threshold_mb=10):
        """检查并归档旧数据
        
        参数:
            days_threshold: 归档超过多少天的数据
            size_threshold_mb: 文件大小超过多少MB时归档
        """
        try:
            # 检查文件大小
            if os.path.exists(self.new_links_file):
                file_size_mb = os.path.getsize(self.new_links_file) / (1024 * 1024)
                
                need_archive = False
                archive_reason = ""
                
                # 检查文件大小是否超过阈值
                if file_size_mb > size_threshold_mb:
                    need_archive = True
                    archive_reason = f"文件大小 ({file_size_mb:.2f}MB) 超过阈值 ({size_threshold_mb}MB)"
                
                # 检查是否有过期数据
                if not need_archive and os.path.exists(self.new_links_file):
                    with open(self.new_links_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    cutoff_date = (datetime.now() - timedelta(days=days_threshold)).strftime("%Y-%m-%d")
                    
                    # 检查是否有需要归档的旧数据
                    old_timestamps = []
                    for timestamp in data.keys():
                        if timestamp.split()[0] < cutoff_date:
                            old_timestamps.append(timestamp)
                    
                    if old_timestamps:
                        need_archive = True
                        archive_reason = f"发现{len(old_timestamps)}条超过{days_threshold}天的数据记录"
                
                # 执行归档
                if need_archive:
                    self._archive_old_data(archive_reason)
        except Exception as e:
            logger.error(f"检查归档时出错: {e}")

    def _archive_old_data(self, reason):
        """归档旧数据"""
        try:
            if not os.path.exists(self.new_links_file):
                return
            
            # 创建归档文件名
            archive_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            archive_filename = f"links_archive_{archive_timestamp}.json"
            archive_path = os.path.join(self.archive_dir, archive_filename)
            
            # 读取当前数据
            with open(self.new_links_file, 'r', encoding='utf-8') as f:
                current_data = json.load(f)
            
            # 复制数据到归档文件
            shutil.copy2(self.new_links_file, archive_path)
            
            # 创建新的数据文件（只保留最近30天的数据）
            cutoff_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            recent_data = {}
            
            for timestamp, data in current_data.items():
                if timestamp.split()[0] >= cutoff_date:
                    recent_data[timestamp] = data
            
            # 保存新数据
            with open(self.new_links_file, 'w', encoding='utf-8') as f:
                json.dump(recent_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"数据已归档: {archive_filename}")
            logger.info(f"归档原因: {reason}")
            logger.info(f"原始数据条目数: {len(current_data)}, 保留数据条目数: {len(recent_data)}")
            
        except Exception as e:
            logger.error(f"归档数据时出错: {e}")

    def read_homepage_urls(self):
        """从Excel文件读取主页URL"""
        try:
            df = pd.read_excel(self.excel_path)
            # 确保必要的列存在
            if 'link' not in df.columns:
                raise ValueError("Excel文件中缺少'link'列")
            
            # 创建URL字典，包含备注和来源信息
            urls_info = {}
            for _, row in df.iterrows():
                url = row['link']
                info = {
                    'note': row.get('备注', ''),
                    'source': row.get('来源', '')
                }
                urls_info[url] = info
            
            return urls_info
        except Exception as e:
            logger.error(f"读取Excel文件时出错: {e}")
            return {}

    def extract_links_from_page(self, url):
        """从页面提取链接"""
        max_retries = config.MAX_RETRIES
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                if retry_count > 0:
                    # 固定15秒等待时间
                    wait_time = 15
                    logger.info(f"第 {retry_count} 次重试，等待 {wait_time} 秒...")
                    time.sleep(wait_time)
                
                logger.info(f"正在使用map方法获取 {url} 的链接...")
                
                # 使用map_url功能获取所有可访问的链接
                result = self.app.map_url(url, params={
                    'includeSubdomains': False,  # 包含子域名
                    'limit': 500,  # 增加链接获取上限
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
                    
                    if len(links) != len(result['links']):
                        logger.info(f"移除了自引用链接: {url}")
                    
                    logger.info(f"原始链接数量: {len(result['links'])}, 去除自引用后: {len(links)}, 过滤后: {len(filtered_links)}")
                    return filtered_links
                
                logger.warning("没有找到链接或返回结果为空")
                return []
                
            except Exception as e:
                logger.error(f"从页面提取链接时出错 {url}: {e}")
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
        urls_info = self.read_homepage_urls()
        if not urls_info:
            logger.warning("没有找到要监控的URL")
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
                historical_links = self.link_history.get(homepage_url, [])
                logger.info(f"历史链接数量: {len(historical_links)}")
                
                # 找出新链接
                new_links = [link for link in current_links if link not in historical_links]
                
                if new_links:
                    logger.info(f"发现 {len(new_links)} 个新链接:")
                    # 限制显示的链接数量，避免输出过长
                    display_limit = min(10, len(new_links))
                    for i, link in enumerate(new_links[:display_limit]):
                        logger.info(f"  - {link}")
                    
                    if len(new_links) > display_limit:
                        logger.info(f"  ... 还有 {len(new_links) - display_limit} 个新链接未显示")
                    
                    # 更新历史记录
                    self.link_history[homepage_url] = list(set(historical_links + current_links))
                    logger.info(f"历史链接更新至 {len(self.link_history[homepage_url])} 个")
                    
                    # 记录新链接
                    new_links_found[homepage_url] = {
                        'note': info['note'],
                        'source': info['source'],
                        'new_links': new_links,
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    total_new_links += len(new_links)
                    
                    # 为每个网站单独保存一次，增强容错性
                    site_new_links = {homepage_url: new_links_found[homepage_url]}
                    self._save_incremental_data(site_new_links)
                    
                else:
                    logger.info("没有发现新链接")
                
                # 每次处理完一个URL后保存历史记录，增强容错性
                self._save_link_history()
                
                # 每次检查后暂停较长时间，避免请求过于频繁
                if processed_urls < total_urls:  # 最后一个URL不需要等待
                    # 固定15秒等待时间
                    wait_time = 15
                    logger.info(f"等待 {wait_time} 秒后继续下一个URL...")
                    time.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"处理主页时出错 {homepage_url}: {e}")
                continue

        # 保存最终的历史记录
        self._save_link_history()
        
        # 如果发现了新链接，保存它们
        if new_links_found:
            self._save_new_links(new_links_found)
            logger.info(f"\n总计发现 {total_new_links} 个新链接，来自 {len(new_links_found)} 个网站")
        else:
            logger.info("\n未发现任何新链接")
    
    def _save_incremental_data(self, site_data):
        """增量保存单个网站的新链接数据"""
        try:
            # 读取现有的新链接数据（如果存在）
            existing_data = {}
            if os.path.exists(self.new_links_file):
                with open(self.new_links_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)

            # 更新数据
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 如果时间戳已存在，合并数据；否则创建新条目
            if timestamp in existing_data:
                for url, data in site_data.items():
                    existing_data[timestamp][url] = data
            else:
                # 生成batch_id
                batch_id = f"batch_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                # 为数据添加batch_id
                for homepage_url in site_data:
                    site_data[homepage_url]['batch_id'] = batch_id
                existing_data[timestamp] = site_data

            # 保存更新后的数据
            with open(self.new_links_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)
                
            logger.debug(f"网站 {list(site_data.keys())[0]} 的数据已增量保存")
        except Exception as e:
            logger.error(f"增量保存数据时出错: {e}")

def main(interval_minutes=None):
    """主函数，可选择定时运行"""
    # 确保Excel文件路径存在
    excel_path = "testhomepage.xlsx"
    
    # 检查Excel文件是否存在，如果不存在，尝试在当前目录下寻找
    if not os.path.exists(excel_path):
        current_dir = os.getcwd()
        excel_path = os.path.join(current_dir, "testhomepage.xlsx")
        
        # 如果还是找不到，显示警告但继续运行
        if not os.path.exists(excel_path):
            logger.warning(f"找不到Excel文件: {excel_path}")
            logger.warning("请确保Excel文件存在或更新路径")
            excel_path = input("请输入Excel文件的路径: ")
    
    logger.info(f"使用Excel文件: {excel_path}")
    monitor = HomepageMonitor(excel_path)
    
    def run_check():
        logger.info(f"\n开始检查 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        monitor.check_for_new_links()
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
                logger.error(f"运行过程中发生错误: {e}")
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
        logger.error(f"程序执行出错: {e}") 