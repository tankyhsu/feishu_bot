import logging
import lark_oapi as lark
from lark_oapi.ws import Client

from config import Config
from utils.logger import setup_logging
from services.task_service import TaskService
from services.minutes_service import MinutesService
from services.doc_service_v2 import DocServiceV2 as DocService
from services.im_service import IMService
from services.llm_service import LLMParser
from services.rss_service_v2 import RSSServiceV2 as RSSService
from handlers.minutes_handler import MinutesHandler
from handlers.message_handler import MessageHandler

def main():
    # 1. Load Config
    try:
        config = Config()
    except Exception as e:
        logging.basicConfig(level=logging.INFO)
        logging.error(f"Failed to load config: {e}")
        return

    # 2. Setup Logging
    setup_logging(config)

    # 3. Init Lark Client
    client = lark.Client.builder() \
        .app_id(config.APP_ID) \
        .app_secret(config.APP_SECRET) \
        .log_level(lark.LogLevel.INFO) \
        .build()

    # Initialize LLMParser
    llm_service = LLMParser(
        api_key=config.LLM_API_KEY,
        base_url=config.LLM_BASE_URL,
        model=config.LLM_MODEL
    )

    # 4. Init Services
    # Core Services
    im_service = IMService(client)
    doc_service = DocService(config.APP_ID, config.APP_SECRET)
    
    # Feature Services
    # TaskService now requires llm_service for semantic matching
    task_service = TaskService(client, config, llm_service=llm_service) 
    
    # RSS Service
    rss_service = RSSService(config, llm_service, doc_service)
    
    # Minutes Service (Previously missing initialization)
    minutes_service = MinutesService(
        app_id=config.APP_ID,
        app_secret=config.APP_SECRET,
        llm_key=config.LLM_API_KEY,
        llm_base=config.LLM_BASE_URL,
        llm_model=config.LLM_MODEL
    )

    # 5. Init Handlers
    # MinutesHandler requires specific services, not client/config
    minutes_handler = MinutesHandler(minutes_service, doc_service, im_service)
    
    message_handler = MessageHandler(config, im_service, task_service, llm_service, minutes_handler, rss_service)

    # 5. Register Event Callback
    event_handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(message_handler.handle) \
        .build()

    # 6. Start WebSocket Client
    ws_client = Client(config.APP_ID, config.APP_SECRET, event_handler=event_handler, log_level=lark.LogLevel.INFO)
    
    print("🤖 Dobby (Refactored) is starting...")
    ws_client.start()

if __name__ == "__main__":
    main()
