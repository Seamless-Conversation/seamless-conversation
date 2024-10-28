import os
from queue import Queue
import time
import logging
import argparse

from src.llm.conversation_manager import *

from src.config.loader import load_config
from src.llm.factory import LLMFactory
from src.stt.factory import STTFactory

DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

def parse_args():
    parser = argparse.ArgumentParser("Seamless conversation with AI")

    parser.add_argument('-overridelog', action='store_true', help='Override logging of external libraries and enable logging')
    parser.add_argument('-stt', help='Set the speech to text model')
    parser.add_argument('-llm', help='Set the large language model')
    parser.add_argument('-disablellmreponse', action='store_true', help='Disable the computation of the LLM response. Used for debugging and testing.', default=False)

    return parser.parse_args()

class ModuleFilter(logging.Filter):
    def filter(self, record):
        return record.name.startswith('src')

def setup_logging(override_log):
    if DEBUG or override_log:
        logging.basicConfig(level=logging.DEBUG) 

    if not override_log:
        return
    root_logger = logging.getLogger()

    filter_module = ModuleFilter()
    root_logger.addFilter(filter_module)

    for logger_name in logging.root.manager.loggerDict:
        logger = logging.getLogger(logger_name)
        logger.addFilter(filter_module)

def main():
    args  = parse_args()
    setup_logging(args.overridelog)

    config = load_config("config.yaml")

    if (args.llm):
        config.llm.provider = args.llm
    if (args.stt):
        config.stt.provider = args.stt

    shared_queue = Queue(maxsize=2000)

    llm_provider = LLMFactory.create(config.llm)
    stt_provider = STTFactory.create(config.stt, shared_queue)

    llm_provider.setup()

    conversation_manager = ConversationManager(llm_provider, 'ai_prompts/system/response_decision_prompt.txt', shared_queue, args.disablellmreponse)

    try:
        conversation_manager.start()
        stt_provider.start()

        while True:
            time.sleep(0.1)

    except KeyboardInterrupt:
        logging.info("Recieved KeyboardInterrupt, stopping.")
        stt_provider.stop()
        conversation_manager.stop()
    except Exception as e:
        logging.critical(f"An error occurred: {e}")
        stt_provider.stop()
        conversation_manager.stop()
        raise

if __name__ == "__main__":
    main()
