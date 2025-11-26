import logging
import lark_oapi as lark
from lark_oapi.ws import Client

from config import Config
from services.task_service import TaskService
from services.minutes_service import MinutesService
from services.doc_service import DocService
from services.im_service import IMService
from services.llm_service import LLMParser
from handlers.minutes_handler import MinutesHandler
from handlers.message_handler import MessageHandler

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    # 1. Load Config
    try:
        config = Config()
    except Exception as e:
        logging.error(f"Failed to load config: {e}")
        return

    # 2. Init Lark Client
    client = lark.Client.builder() \
        .app_id(config.APP_ID) \
        .app_secret(config.APP_SECRET) \
        .log_level(lark.LogLevel.INFO) \
        .build()

    # 3. Init Services
    im_service = IMService(client)
    task_service = TaskService(client, config)
    minutes_service = MinutesService(
        config.APP_ID, 
        config.APP_SECRET,
        config.LLM_API_KEY,
        config.LLM_BASE_URL,
        config.LLM_MODEL
    )
    doc_service = DocService(config.APP_ID, config.APP_SECRET)
    llm_service = LLMParser(
        api_key=config.LLM_API_KEY,
        base_url=config.LLM_BASE_URL,
        model=config.LLM_MODEL
    )

    # 4. Init Handlers
    minutes_handler = MinutesHandler(minutes_service, doc_service, im_service)
    message_handler = MessageHandler(config, im_service, task_service, llm_service, minutes_handler)

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
