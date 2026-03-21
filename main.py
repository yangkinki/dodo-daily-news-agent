#!/usr/bin/env python3
"""
智能新闻聚合推送系统
- 多源 RSS 抓取
- 智能去重
- 多渠道推送
"""

import feedparser
import requests
import os
import json
import yaml
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 测试数据（用于本地测试流程）
TEST_NEWS = [
    {
        "title": "OpenAI发布GPT-5预览版，多模态能力大幅提升",
        "summary": "OpenAI今日发布了GPT-5的预览版本，新版本在图像理解、视频分析和代码生成方面都有显著改进，支持更长的上下文窗口...",
        "link": "https://example.com/news/1",
        "category": "人工智能",
        "source_name": "AI前沿"
    },
    {
        "title": "苹果WWDC 2026宣布：AI功能将成iOS 20核心",
        "summary": "苹果公司宣布WWDC 2026开发者大会将于6月举行，预计将发布iOS 20，其中AI驱动的Siri升级将是最大亮点...",
        "link": "https://example.com/news/2",
        "category": "科技动态",
        "source_name": "科技早报"
    },
    {
        "title": "美联储维持利率不变，科技股集体上涨",
        "summary": "美联储最新利率决议维持基准利率不变，市场反应积极，纳斯达克指数上涨2.3%，大型科技股普遍走高...",
        "link": "https://example.com/news/3",
        "category": "财经要闻",
        "source_name": "财经观察"
    },
    {
        "title": "Python 3.14发布，性能提升40%",
        "summary": "Python基金会正式发布Python 3.14版本，新版本通过改进解释器和内存管理，整体性能提升约40%...",
        "link": "https://example.com/news/4",
        "category": "开源技术",
        "source_name": "开源中国"
    }
]


class NewsCache:
    """新闻去重缓存"""
    
    def __init__(self, cache_file: str, retention_days: int = 7):
        self.cache_file = Path(cache_file)
        self.retention_days = retention_days
        self.sent_urls = self._load()
    
    def _load(self) -> set:
        """加载已发送的新闻URL"""
        if not self.cache_file.exists():
            return set()
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 清理过期记录
            cutoff = datetime.now() - timedelta(days=self.retention_days)
            valid_urls = {
                url for url, timestamp in data.items()
                if datetime.fromisoformat(timestamp) > cutoff
            }
            logger.info(f"缓存加载完成，有效记录: {len(valid_urls)} 条")
            return valid_urls
        except Exception as e:
            logger.error(f"缓存加载失败: {e}")
            return set()
    
    def save(self):
        """保存缓存"""
        try:
            data = {url: datetime.now().isoformat() for url in self.sent_urls}
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"缓存保存完成，共 {len(self.sent_urls)} 条")
        except Exception as e:
            logger.error(f"缓存保存失败: {e}")
    
    def is_sent(self, url: str) -> bool:
        """检查是否已发送"""
        return url in self.sent_urls
    
    def mark_sent(self, url: str):
        """标记为已发送"""
        self.sent_urls.add(url)


class NewsFetcher:
    """新闻抓取器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.cache = NewsCache(
            config['cache']['file'],
            config['cache']['retention_days']
        )
    
    def clean_html(self, html: str) -> str:
        """清理HTML标签"""
        if not html:
            return ""
        soup = BeautifulSoup(html, 'html.parser')
        return soup.get_text(separator=' ', strip=True)
    
    def fetch_source(self, source: Dict, hours_limit: int) -> List[Dict]:
        """从单个源抓取新闻"""
        if not source.get('enabled', True):
            return []
        
        name = source['name']
        url = source['url']
        max_items = source.get('max_items', 2)
        
        logger.info(f"正在抓取: {name}")
        
        try:
            feed = feedparser.parse(url)
            
            if feed.bozo:
                logger.warning(f"{name} 解析警告: {feed.bozo_exception}")
            
            items = []
            cutoff_time = datetime.now() - timedelta(hours=hours_limit)
            
            for entry in feed.entries[:max_items * 2]:  # 多取一些用于过滤
                # 解析发布时间
                pub_time = None
                if entry.get('published_parsed'):
                    pub_time = datetime(*entry.published_parsed[:6])
                elif entry.get('updated_parsed'):
                    pub_time = datetime(*entry.updated_parsed[:6])
                else:
                    pub_time = datetime.now()
                
                # 只取限定时间内的新闻
                if pub_time < cutoff_time:
                    continue
                
                link = entry.get('link', '')
                
                # 去重检查
                if self.cache.is_sent(link):
                    logger.debug(f"跳过已发送: {link}")
                    continue
                
                title = entry.get('title', '无标题').replace('\n', ' ').strip()
                summary = self.clean_html(entry.get('summary', ''))[:300]
                
                items.append({
                    'title': title,
                    'summary': summary or "暂无摘要",
                    'link': link,
                    'pub_time': pub_time,
                    'source_name': name,
                    'category': source.get('category', '其他')
                })
                
                if len(items) >= max_items:
                    break
            
            logger.info(f"{name} 抓取到 {len(items)} 条新新闻")
            return items
            
        except Exception as e:
            logger.error(f"{name} 抓取失败: {e}")
            return []
    
    def fetch_all(self) -> Dict[str, List[Dict]]:
        """抓取所有源的新闻"""
        hours_limit = self.config['fetch']['hours_limit']
        sources = self.config['news_sources']
        
        all_news = {}
        total = 0
        
        for source in sources:
            items = self.fetch_source(source, hours_limit)
            if items:
                category = source.get('category', '其他')
                if category not in all_news:
                    all_news[category] = []
                all_news[category].extend(items)
                total += len(items)
        
        logger.info(f"总共抓取到 {total} 条新新闻")
        return all_news


class PushService:
    """推送服务"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.sct_key = os.environ.get('SCT_KEY', '')
        self.bark_key = os.environ.get('BARK_KEY', '')
    
    def format_message(self, news_by_category: Dict[str, List[Dict]]) -> str:
        """格式化消息内容"""
        lines = []
        
        for category, items in sorted(news_by_category.items()):
            lines.append(f"\n📂 **{category}**\n")
            
            for item in items:
                source = item['source_name']
                title = item['title']
                summary = item['summary']
                link = item['link']
                
                lines.append(
                    f"🔹 **【{source}】** {title}\n"
                    f"   > {summary}\n"
                    f"   👉 [查看详情]({link})\n"
                )
        
        return '\n'.join(lines)
    
    def send_server_chan(self, title: str, content: str) -> bool:
        """推送到Server酱（微信）"""
        # 检查key是否配置（只显示前5位用于调试）
        if not self.sct_key:
            logger.error("❌ 未配置 SCT_KEY，跳过微信推送")
            logger.error("   请检查 GitHub Secrets 是否设置了 SCT_KEY")
            return False
        
        # 显示key的前5位用于调试（安全考虑不显示完整key）
        key_preview = self.sct_key[:5] + "..." if len(self.sct_key) > 5 else "***"
        logger.info(f"📤 使用 SCT_KEY: {key_preview} 进行推送")
        
        try:
            logger.info(f"📤 推送标题: {title[:50]}...")
            logger.info(f"📤 推送内容长度: {len(content)} 字符")
            
            resp = requests.post(
                f"https://sctapi.ftqq.com/{self.sct_key}.send",
                data={"title": title, "desp": content},
                timeout=30
            )
            
            logger.info(f"📤 Server酱响应状态码: {resp.status_code}")
            
            try:
                result = resp.json()
                logger.info(f"📤 Server酱响应: {result}")
            except:
                logger.warning(f"📤 Server酱非JSON响应: {resp.text[:200]}")
                result = {}
            
            # Server酱返回的错误码判断
            # 新版API：成功时 code=0, data.error='SUCCESS', data.errno=0
            code = result.get("code")
            data = result.get("data", {})
            data_errno = data.get("errno")
            data_error = data.get("error", "")
            
            if code == 0 and data_error == "SUCCESS":
                logger.info("✅ 微信推送成功")
                logger.info(f"   推送ID: {data.get('pushid', 'N/A')}")
                return True
            else:
                error_msg = result.get('message') or data_error or '未知错误'
                logger.error(f"❌ 微信推送失败: {error_msg}")
                logger.error(f"   完整响应: {result}")
                return False
        except requests.exceptions.Timeout:
            logger.error("❌ 微信推送超时 (30s)")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 微信推送请求异常: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 微信推送异常: {e}")
            return False
    
    def send_bark(self, title: str, content: str) -> bool:
        """推送到Bark（iOS）"""
        if not self.bark_key:
            logger.warning("未配置 BARK_KEY，跳过Bark推送")
            return False
        
        try:
            # 截取前100字符作为Bark内容
            short_content = content[:100] + "..." if len(content) > 100 else content
            resp = requests.post(
                f"https://api.day.app/{self.bark_key}/{title}/{short_content}",
                timeout=30
            )
            if resp.status_code == 200:
                logger.info("✅ Bark推送成功")
                return True
            else:
                logger.error(f"❌ Bark推送失败: {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Bark推送异常: {e}")
            return False
    
    def send(self, news_by_category: Dict[str, List[Dict]]) -> bool:
        """执行所有配置的推送"""
        if not news_by_category:
            logger.info("⚠️ 没有新新闻需要推送")
            return False
        
        today = datetime.now().strftime('%Y-%m-%d')
        title = f"📰 科技日报 | {today}"
        content = self.format_message(news_by_category)
        
        push_config = self.config.get('push', {})
        success = False
        
        # Server酱推送
        if push_config.get('server_chan', {}).get('enabled', True):
            if self.send_server_chan(title, content):
                success = True
        
        # Bark推送
        if push_config.get('bark', {}).get('enabled', False):
            if self.send_bark(title, content):
                success = True
        
        return success


def load_config() -> Dict:
    """加载配置文件"""
    config_path = Path(__file__).parent / 'config.yml'
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"配置文件加载失败: {e}")
        raise


def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("开始执行新闻抓取任务")
    logger.info("=" * 50)
    
    # 检查是否使用测试模式
    test_mode = os.environ.get('TEST_MODE', 'false').lower() == 'true'
    
    try:
        # 加载配置
        config = load_config()
        
        # 初始化组件
        fetcher = NewsFetcher(config)
        pusher = PushService(config)
        
        if test_mode:
            # 测试模式：使用本地测试数据
            logger.info("🧪 运行测试模式，使用模拟数据")
            news_by_category = {}
            for item in TEST_NEWS:
                category = item['category']
                if category not in news_by_category:
                    news_by_category[category] = []
                # 添加时间戳
                item['pub_time'] = datetime.now()
                news_by_category[category].append(item)
            logger.info(f"测试数据加载完成，共 {len(TEST_NEWS)} 条")
        else:
            # 正常模式：抓取新闻
            news_by_category = fetcher.fetch_all()
        
        if not news_by_category:
            logger.info("今日没有新新闻，任务结束")
            return
        
        # 打印要推送的内容预览
        logger.info("\n" + "=" * 50)
        logger.info("📋 推送内容预览：")
        logger.info("=" * 50)
        for category, items in news_by_category.items():
            logger.info(f"\n📂 {category} ({len(items)}条)")
            for item in items:
                logger.info(f"  • {item['title'][:50]}...")
        
        # 推送新闻
        logger.info("\n" + "=" * 50)
        if pusher.send(news_by_category):
            # 标记为已发送
            for category, items in news_by_category.items():
                for item in items:
                    fetcher.cache.mark_sent(item['link'])
            fetcher.cache.save()
            logger.info("✅ 任务完成")
        else:
            logger.error("❌ 推送失败，未标记为已发送")
            
    except Exception as e:
        logger.error(f"❌ 任务执行失败: {e}", exc_info=True)


if __name__ == "__main__":
    main()
