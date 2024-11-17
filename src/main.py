import os
from queue import Queue
import time
import argparse
import logging
from src.config.loader import load_config
from src.event.eventbus import EventBus
from src.dialogue_manager import DialogueManager
from src.llm.factory import LLMFactory
from src.stt.factory import STTFactory
from src.tts.factory import TTSFactory
from src.conversation_group import Speaker
from src.event.eventbus import EventBus, Event
from src.event.event_types import EventType

DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

def parse_args():
    parser = argparse.ArgumentParser("Seamless conversation with AI")

    parser.add_argument('-overridelog', action='store_true', help='Override logging of external libraries and enable logging')
    parser.add_argument('-stt', help='Set the speech to text model')
    parser.add_argument('-tts', help='Set the text to speech model')
    parser.add_argument('-llm', help='Set the large language model')
    # parser.add_argument('-disablellmresponse', action='store_true', help='Disable the computation of the LLM response. Used for debugging and testing.', default=False)

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

    config = load_config("config.yaml")

    if (args.llm):
        config.llm.provider = args.llm
    if (args.stt):
        config.stt.provider = args.stt
    if (args.tts):
        config.tts.provider = args.tts

    # Enable initial logging, we need a better solution here.
    setup_logging(args.overridelog)

    event_bus = EventBus()

    dialogue_manager = DialogueManager(event_bus)

    stt_provider = STTFactory.create(event_bus, config.stt)
    llm_provider = LLMFactory.create(event_bus, config.llm)
    tts_provider = TTSFactory.create(event_bus, config.tts)

    # "Temporary" group. We want to init these based upon config/enviorment
    group_a = dialogue_manager.create_group("group_a")
    group_a.add_member(Speaker("user", event_bus))
    ai = Speaker("Sam", event_bus) # example agent

    ai.set_personality("ai_prompts/npc_personalities/npc_sam")
    group_a.add_member(ai)

    # Setup logging here, libs need to be imported
    # before we can filter for them.
    setup_logging(args.overridelog)

    stt_provider.start()
    llm_provider.start()
    tts_provider.start()

    try:
        while True:
            time.sleep(0.1)

    except KeyboardInterrupt:
        logging.info("Recieved KeyboardInterrupt, stopping.")
        stt_provider.stop()
        llm_provider.stop()
        tts_provider.stop()
        event_bus.shutdown()

if __name__ == "__main__":
    main()