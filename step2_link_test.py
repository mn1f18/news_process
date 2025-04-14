import os
import json
from http import HTTPStatus
from dashscope import Application
import config
import logging
from datetime import datetime
import uuid

# 配置日志系统
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
log_file = os.path.join(log_dir, f"link_test_{datetime.now().strftime('%Y%m%d')}.log")

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()  # 同时输出到控制台
    ]
)
logger = logging.getLogger("LinkTest")

# 检查环境变量是否正确设置
if not config.check_env_vars():
    logger.error("环境变量配置错误，请检查.env文件")
    exit(1)

class LinkAnalyzer:
    """链接分析器，判断链接是否需要爬取"""
    
    def __init__(self, data_dir=None, valid_links_file=None, invalid_links_file=None):
        """初始化链接分析器
        
        参数:
            data_dir: 数据目录，如果指定了valid_links_file和invalid_links_file则忽略此参数
            valid_links_file: 有效链接存储文件路径
            invalid_links_file: 无效链接存储文件路径
        """
        # 如果指定了文件路径，直接使用
        if valid_links_file and invalid_links_file:
            self.valid_links_file = valid_links_file
            self.invalid_links_file = invalid_links_file
            self.status_file = os.path.join(os.path.dirname(valid_links_file), "link_status.json")
        # 否则基于data_dir构建路径（向后兼容）
        elif data_dir:
            self.valid_links_file = os.path.join(data_dir, "valid_links.json")
            self.invalid_links_file = os.path.join(data_dir, "invalid_links.json")
            self.status_file = os.path.join(data_dir, "link_status.json")
        else:
            # 默认路径
            self.valid_links_file = "data/valid_links.json"
            self.invalid_links_file = "data/invalid_links.json"
            self.status_file = "data/link_status.json"
            
        # 确保文件存在
        self._ensure_file_exists(self.valid_links_file)
        self._ensure_file_exists(self.invalid_links_file)
        self._ensure_file_exists(self.status_file)
        
        # 使用config.py中定义的APP_ID
        self.app_id = config.LINK_ANALYZER_APP_ID
        
        logger.info(f"使用百炼应用ID: {self.app_id}")
        
    def _ensure_file_exists(self, file_path):
        """确保文件存在，如果不存在则创建空文件"""
        if not os.path.exists(os.path.dirname(file_path)):
            os.makedirs(os.path.dirname(file_path))
        if not os.path.exists(file_path):
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False)
        
    def _extract_json_from_text(self, text):
        """从文本中提取JSON内容"""
        try:
            # 查找第一个{和最后一个}之间的内容
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1:
                json_str = text[start:end+1]
                return json.loads(json_str)
            return None
        except json.JSONDecodeError:
            logger.error(f"JSON解析失败: {text}")
            return None
        
    def analyze_link(self, link, link_id=None):
        """分析单个链接，返回分析结果和链接ID"""
        if link_id is None:
            link_id = str(uuid.uuid4())
            
        try:
            # 更新链接状态为"分析中"
            self.update_link_status(link_id, link, "ANALYZING")
            
            response = Application.call(
                api_key=config.DASHSCOPE_API_KEY,
                app_id=self.app_id,
                prompt=link  # 直接传入链接作为prompt
            )
            
            if response.status_code != HTTPStatus.OK:
                logger.error(f'请求失败: {response.message}')
                self.update_link_status(link_id, link, "FAILED", error=response.message)
                return None, link_id
                
            # 解析返回的JSON
            result = self._extract_json_from_text(response.output.text)
            if result:
                # 判断链接是否有效
                is_valid = result.get('need_crawl', False)
                status = "VALID" if is_valid else "INVALID"
                
                # 更新链接状态
                self.update_link_status(link_id, link, status, result=result)
                
                # 保存分析结果
                self.save_result(link, result, is_valid, link_id)
                return result, link_id
            else:
                logger.error(f"无法从响应中提取JSON: {response.output.text}")
                self.update_link_status(link_id, link, "FAILED", error="无法解析JSON响应")
                return None, link_id
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"分析链接时出错: {error_msg}")
            self.update_link_status(link_id, link, "FAILED", error=error_msg)
            return None, link_id

    def update_link_status(self, link_id, link, status, result=None, error=None):
        """更新链接状态"""
        try:
            status_data = {}
            if os.path.exists(self.status_file):
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    status_data = json.load(f)
            
            # 更新状态
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if link_id not in status_data:
                status_data[link_id] = {
                    'link': link,
                    'created_at': timestamp,
                    'history': []
                }
            
            # 添加新状态记录
            new_status = {
                'status': status,
                'timestamp': timestamp
            }
            
            if result:
                new_status['result'] = result
            
            if error:
                new_status['error'] = error
            
            status_data[link_id]['history'].append(new_status)
            status_data[link_id]['current_status'] = status
            status_data[link_id]['updated_at'] = timestamp
            
            # 保存状态数据
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, ensure_ascii=False, indent=2)
                
            logger.debug(f"链接 {link_id} 状态已更新为 {status}")
            
        except Exception as e:
            logger.error(f"更新链接状态时出错: {e}")

    def save_result(self, link, result, is_valid, link_id):
        """保存分析结果"""
        try:
            # 选择保存文件
            target_file = self.valid_links_file if is_valid else self.invalid_links_file
            
            # 读取现有数据
            existing_data = {}
            if os.path.exists(target_file):
                with open(target_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            
            # 添加新数据
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if timestamp not in existing_data:
                existing_data[timestamp] = {}
            
            existing_data[timestamp][link] = {
                'link_id': link_id,
                'result': result,
                'analyzed_at': timestamp
            }
            
            # 保存数据
            with open(target_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"链接分析结果已保存到 {target_file}")
            
        except Exception as e:
            logger.error(f"保存结果时出错: {e}")

    def get_link_status(self, link_id):
        """获取链接状态"""
        try:
            if os.path.exists(self.status_file):
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    status_data = json.load(f)
                
                if link_id in status_data:
                    return status_data[link_id]
            
            return None
        except Exception as e:
            logger.error(f"获取链接状态时出错: {e}")
            return None

    def get_all_link_status(self, status_filter=None):
        """获取所有链接状态，可选按状态筛选"""
        try:
            if os.path.exists(self.status_file):
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    status_data = json.load(f)
                
                if status_filter:
                    return {k: v for k, v in status_data.items() 
                            if v.get('current_status') == status_filter}
                return status_data
            
            return {}
        except Exception as e:
            logger.error(f"获取所有链接状态时出错: {e}")
            return {}

    def process_links(self, links, batch_id=None):
        """处理多个链接，支持批处理ID"""
        if batch_id is None:
            batch_id = f"batch_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
        results = {
            'batch_id': batch_id,
            'valid': [],
            'invalid': [],
            'failed': [],
            'link_ids': {}
        }
        
        total_links = len(links)
        processed_links = 0
        
        for link in links:
            processed_links += 1
            link_id = f"{batch_id}_{processed_links}"
            logger.info(f"\n正在分析链接 [{processed_links}/{total_links}]: {link}")
            
            result, link_id = self.analyze_link(link, link_id)
            # 将链接ID添加到结果中
            results['link_ids'][link] = link_id
            
            if result:
                is_valid = result.get('need_crawl', False)
                if is_valid:
                    results['valid'].append(link)
                    logger.info(f"有效链接: {link}")
                    logger.info(f"原因: {result.get('reason', '')}")
                    logger.info(f"置信度: {result.get('confidence', 0)}")
                else:
                    results['invalid'].append(link)
                    logger.info(f"无效链接: {link}")
                    logger.info(f"原因: {result.get('reason', '')}")
                    logger.info(f"置信度: {result.get('confidence', 0)}")
            else:
                results['failed'].append(link)
                logger.warning(f"无法分析链接: {link}")
        
        return results

    def reanalyze_failed_links(self, max_retries=3):
        """重新分析失败的链接"""
        failed_links = self.get_all_link_status("FAILED")
        retry_links = []
        
        for link_id, data in failed_links.items():
            # 检查重试次数
            retry_count = sum(1 for status in data.get('history', []) 
                             if status.get('status') == "FAILED")
            
            if retry_count < max_retries:
                retry_links.append((link_id, data['link']))
        
        if not retry_links:
            logger.info("没有需要重试的失败链接")
            return []
        
        logger.info(f"开始重试 {len(retry_links)} 个失败的链接分析")
        results = []
        
        for link_id, link in retry_links:
            logger.info(f"重试分析链接: {link} (ID: {link_id})")
            result, _ = self.analyze_link(link, link_id)
            if result:
                results.append((link_id, link, result))
        
        return results

def main():
    """主函数"""
    # 示例链接列表
    test_links = [
        "https://example.com/agriculture-news",
        "https://example.com/farming-policy",
        "https://example.com/weather-impact"
    ]
    
    analyzer = LinkAnalyzer()
    results = analyzer.process_links(test_links)
    
    logger.info("\n分析结果统计:")
    logger.info(f"批次ID: {results['batch_id']}")
    logger.info(f"有效链接数量: {len(results['valid'])}")
    logger.info(f"无效链接数量: {len(results['invalid'])}")
    logger.info(f"失败链接数量: {len(results['failed'])}")
    
    if results['valid']:
        logger.info("\n有效链接列表:")
        for link in results['valid']:
            logger.info(f"- {link} (ID: {results['link_ids'][link]})")
    
    if results['invalid']:
        logger.info("\n无效链接列表:")
        for link in results['invalid']:
            logger.info(f"- {link} (ID: {results['link_ids'][link]})")
    
    if results['failed']:
        logger.info("\n失败链接列表:")
        for link in results['failed']:
            logger.info(f"- {link} (ID: {results['link_ids'][link]})")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("检测到用户中断，程序退出")
    except Exception as e:
        logger.error(f"程序执行出错: {e}") 