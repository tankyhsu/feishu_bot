import logging
import logging.handlers
import os
import sys

def setup_logging(config):
    """
    Setup logging configuration with rotation.
    Reads configuration from the passed Config object.
    """
    # Get config values with defaults
    log_file = getattr(config, 'LOG_FILE', 'logs/bot.log')
    log_max_bytes = getattr(config, 'LOG_MAX_BYTES', 10 * 1024 * 1024) # 10MB default
    log_backup_count = getattr(config, 'LOG_BACKUP_COUNT', 5) # 5 backups default
    log_level_str = getattr(config, 'LOG_LEVEL', 'INFO')
    
    # Map string level to logging constant
    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    log_level = level_map.get(log_level_str.upper(), logging.INFO)

    # Ensure log directory exists
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except OSError as e:
            print(f"Error creating log directory {log_dir}: {e}", file=sys.stderr)
            # Continue to at least setup console logging
            pass

    # Configure Root Logger
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # Clear existing handlers to avoid duplication if called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s')

    # Handler 1: Rotating File
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=log_max_bytes, backupCount=log_backup_count, encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Failed to setup file logging to {log_file}: {e}", file=sys.stderr)

    # Handler 2: Console (Stream)
    # Use stdout so supervisor captures it in bot_out.log (or separate it if we want)
    # But usually we want logs in both or just file. 
    # If we log to file AND console, and supervisor captures console to file, we have duplication.
    # However, for interactive running, console is needed.
    # We will keep console handler.
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logging.info(f"Logging configured. Level: {log_level_str}, File: {log_file}, MaxBytes: {log_max_bytes}, Backups: {log_backup_count}")
