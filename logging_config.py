import logging
import os
from logging.handlers import RotatingFileHandler

LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

LOG_FILE = os.path.join(LOGS_DIR, 'app.log')

logger = logging.getLogger('MinecraftCrafterGathererGuild')
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
file_handler = RotatingFileHandler(LOG_FILE, encoding='utf-8')

console_handler.setLevel(logging.INFO)
file_handler.setLevel(logging.DEBUG)

log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
console_handler.setFormatter(log_format)
file_handler.setFormatter(log_format)

logger.addHandler(console_handler)
logger.addHandler(file_handler)
