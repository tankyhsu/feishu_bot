import feedparser
import time
import logging
import requests
from datetime import datetime, timedelta

class RSSService:
    def __init__(self, config, llm_service, doc_service):
        self.feeds = config.FEEDS
        self.llm = llm_service
        self.doc = doc_service
        self.time_window = timedelta(hours=24)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

    def fetch_and_summarize(self):
        if not self.feeds:
            return "⚠️ 未配置 RSS 订阅源 (config.json -> FEEDS)"

        articles = []
        now = datetime.now()
        
        logging.info(f"📡 Starting RSS fetch for {len(self.feeds)} feeds...")

        for feed_conf in self.feeds:
            name = feed_conf.get("name", "Unknown")
            url = feed_conf.get("url")
            if not url: continue

            try:
                # 1. Fetch Content
                try:
                    resp = requests.get(url, headers=self.headers, timeout=20)
                    resp.raise_for_status()
                    content = resp.text
                except Exception as e:
                    logging.error(f"⚠️ Failed to fetch {name}: {e}")
                    continue

                # 2. Parse Feed
                feed = feedparser.parse(content)
                
                for entry in feed.entries:
                    # 3. Time Filter
                    published_time = self._get_published_time(entry)
                    if published_time:
                        if now - published_time <= self.time_window:
                            articles.append({
                                'source': name,
                                'title': entry.title,
                                'link': entry.link,
                                'summary': self._clean_summary(entry),
                                'image': self._extract_image_url(entry)
                            })
            except Exception as e:
                logging.error(f"❌ Error processing feed {name}: {e}")

        logging.info(f"✅ Fetched {len(articles)} articles.")

        if not articles:
            return "📭 过去 24 小时没有新内容。"

        # 4. Prepare Text for LLM
        articles_text = ""
        for i, art in enumerate(articles):
            articles_text += f"Index: {i}\nSource: {art['source']}\nTitle: {art['title']}\nLink: {art['link']}\nSummary: {art['summary'][:300]}\n\n"

        # 5. LLM Analyze
        analysis = self.llm.analyze_rss(articles_text)
        if not analysis:
            return "❌ AI 分析失败，请查看日志。"

        # 6. Create Doc
        date_str = now.strftime("%Y-%m-%d")
        doc_title = f"📅 AI 早报 - {date_str}"
        doc_id = self.doc.create_document(doc_title)
        
        if not doc_id:
            return "❌ 文档创建失败。"

        # 7. Build Doc Content
        blocks = []
        
        # Intro
        daily_insight = analysis.get("daily_insight", "今日无特殊洞察。")
        blocks.append(self.doc.create_heading_block("每日洞察", 2))
        blocks.append(self.doc.create_text_block(daily_insight))
        
        # Articles
        for item in analysis.get("articles", []):
            idx = item.get("original_index")
            if idx is None or idx >= len(articles): continue
            
            original_art = articles[idx]
            
            # Title (H3, no link to avoid invalid param)
            title_text = f"{item.get('title', original_art['title'])} ({item.get('category', 'General')})"
            blocks.append(self.doc.create_heading_block(title_text, 3))
            
            # Summary (Text)
            summary_text = item.get("summary", "-")
            blocks.append(self.doc.create_text_block(summary_text))
            
            # Link
            blocks.append(self.doc.create_text_block("🔗 阅读原文", original_art['link']))
            
            # Divider (Removed for stability)
            # blocks.append(self.doc.create_divider_block())

        # 8. Write to Doc
        self.doc.add_content(doc_id, blocks)
        
        doc_url = f"https://feishu.cn/docx/{doc_id}"
        
        return f"📅 **{date_str} AI 早报已生成**\n\n💡 {daily_insight}\n\n[📄 点击查看完整图文报告]({doc_url})"

    def _extract_image_url(self, entry):
        # 1. Media Content (RSS extension)
        if 'media_content' in entry:
            for media in entry.media_content:
                if 'image' in media.get('type', '') or 'medium' in media and media['medium'] == 'image':
                    if 'url' in media: return media['url']
        
        # 2. Links (Atom/RSS)
        if 'links' in entry:
            for link in entry.links:
                if 'image' in link.get('type', ''):
                    return link.get('href')
                
        # 3. Enclosures
        if 'enclosures' in entry:
            for enc in entry.enclosures:
                if 'image' in enc.get('type', ''):
                    return enc.get('href')
                    
        return None

    def _get_published_time(self, entry):
        dt_struct = entry.get('published_parsed') or entry.get('updated_parsed')
        if dt_struct:
            return datetime.fromtimestamp(time.mktime(dt_struct))
        return None

    def _clean_summary(self, entry):
        s = entry.get('summary', '')
        return s.replace("\n", " ").strip()
