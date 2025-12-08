import sys
import os
import logging
import lark_oapi as lark

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from utils.logger import setup_logging
from services.im_service import IMService
from services.doc_service_v2 import DocServiceV2 as DocService
from services.llm_service import LLMParser
from services.rss_service_v2 import RSSServiceV2 as RSSService

def main():
    # 1. Load Config
    try:
        config = Config()
    except Exception as e:
        logging.basicConfig(level=logging.INFO)
        logging.error(f"Failed to load config: {e}")
        return

    # Setup Logging
    setup_logging(config)
    
    logging.info("🚀 Starting Daily RSS Push...")

    chat_id = config.DAILY_PUSH_CHAT_ID
    if not chat_id:
        logging.error("❌ Missing DAILY_PUSH_CHAT_ID in config.json. Cannot send push.")
        return

    # 2. Init Lark Client
    client = lark.Client.builder() \
        .app_id(config.APP_ID) \
        .app_secret(config.APP_SECRET) \
        .log_level(lark.LogLevel.WARNING) \
        .build()

    # 3. Init Services
    im_service = IMService(client)
    doc_service = DocService(config.APP_ID, config.APP_SECRET)
    llm_service = LLMParser(
        api_key=config.LLM_API_KEY,
        base_url=config.LLM_BASE_URL,
        model=config.LLM_MODEL
    )
    rss_service = RSSService(config, llm_service, doc_service)

    # 4. Fetch & Summarize
    logging.info("📰 Fetching and summarizing feeds...")
    digest = rss_service.fetch_and_summarize()

    # 5. Send Message
    logging.info(f"📤 Sending digest to chat_id: {chat_id}")
    msg_id = im_service.send(chat_id, digest, receive_id_type="chat_id")
    
    if msg_id:
        logging.info("✅ Daily push sent successfully!")
    else:
        logging.error("❌ Failed to send daily push.")

if __name__ == "__main__":
    main()
