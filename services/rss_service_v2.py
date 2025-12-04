import feedparser
import time
import logging
import requests
import re
from datetime import datetime, timedelta

class RSSServiceV2:
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
                resp = requests.get(url, headers=self.headers, timeout=20)
                if resp.status_code != 200: continue
                feed = feedparser.parse(resp.text)
                for entry in feed.entries:
                    published_time = self._get_published_time(entry)
                    if published_time and (now - published_time <= self.time_window):
                        articles.append({
                            'source': name,
                            'title': entry.title,
                            'link': entry.link,
                            'summary': self._clean_summary(entry),
                            'image': self._extract_image_url(entry),
                            'category': feed_conf.get('category', 'General')
                        })
            except Exception as e:
                logging.error(f"❌ Error processing feed {name}: {e}")

        logging.info(f"✅ Fetched {len(articles)} articles.")
        if not articles: return "📭 过去 24 小时没有新内容。"

        # LLM Analyze
        articles_text = ""
        for i, art in enumerate(articles):
            articles_text += f"Index: {i}\nSource: {art['source']}\nTitle: {art['title']}\nLink: {art['link']}\nSummary: {art['summary'][:300]}\n\n"

        analysis = self.llm.analyze_rss(articles_text)
        if not analysis: return "❌ AI 分析失败。"

        # Create Doc
        date_str = now.strftime("%Y-%m-%d")
        doc_title = f"📅 AI 早报 - {date_str}"
        doc_id = self.doc.create_document(doc_title)
        if not doc_id: return "❌ 文档创建失败。"

        # 2. Build Blocks & Track Images
        blocks = []
        image_map = {} # { block_index: img_url }

        # Intro
        daily_insight = analysis.get("daily_insight", "今日无特殊洞察。")
        blocks.append(self.doc.create_heading_block("每日洞察", 2))
        blocks.append(self.doc.create_text_block(daily_insight))
        
        # Articles
        for item in analysis.get("articles", []):
            idx = item.get("original_index")
            if idx is None or idx >= len(articles): continue
            original_art = articles[idx]
            
            # Title (Clickable H3)
            title_text = f"{item.get('title', original_art['title'])} ({item.get('category', 'General')})"
            blocks.append(self.doc.create_heading_block(title_text, 3, link_url=original_art['link']))
            
            # Image Placeholder (Create empty image block)
            img_url = original_art.get('image')
            if img_url:
                blocks.append(self.doc.create_image_block(None))
                image_map[len(blocks) - 1] = img_url # Track index in the flat list
            
            # Summary (Text)
            summary_text = original_art.get("summary", "无摘要")
            blocks.append(self.doc.create_text_block(summary_text))
            
            # Link
            blocks.append(self.doc.create_text_block("🔗 阅读原文", original_art['link']))
            
            # Divider
            blocks.append(self.doc.create_divider_block())

        # 3. Add Blocks to Doc
        created_blocks = self.doc.add_content(doc_id, blocks)
        if not created_blocks: return "❌ 内容写入失败。"

        # 4. Upload & Replace Images (The 3-step fix)
        logging.info(f"🖼️ Starting image upload for {len(image_map)} images...")
        
        # Note: created_blocks might be longer/shorter if errors occurred, but typically it matches 1:1 for top-level blocks
        # created_blocks is a list of {'block_id': '...', 'block_type': ...}
        
        for blk_idx, img_url in image_map.items():
            if blk_idx >= len(created_blocks): continue
            
            block_id = created_blocks[blk_idx].get("block_id")
            if not block_id: continue
            
            # Download Real Image
            try:
                down = requests.get(img_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
                if down.status_code == 200:
                    # Upload using block_id as parent (Step 2)
                    real_token = self.doc.upload_file("image.jpg", down.content, "docx_image", block_id)
                    
                    if real_token:
                        # Update Block (Step 3)
                        self.doc.update_image_block(doc_id, block_id, real_token)
            except Exception as e:
                logging.error(f"Failed to process image {img_url}: {e}")

        doc_url = f"https://feishu.cn/docx/{doc_id}"
        return f"📅 **{date_str} AI 早报已生成**\n\n💡 {daily_insight}\n\n[📄 点击查看完整图文报告]({doc_url})"

    def _extract_image_url(self, entry):
        if 'media_content' in entry:
            for media in entry.media_content:
                if 'image' in media.get('type', '') or 'medium' in media and media['medium'] == 'image':
                    return media.get('url')
        if 'links' in entry:
            for link in entry.links:
                if 'image' in link.get('type', ''):
                    return link.get('href')
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
        s = re.sub('<[^<]+?>', '', s)
        return s.replace("\n", " ").strip()